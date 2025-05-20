import os
import boto3
from botocore.exceptions import ClientError
from flask import current_app
import mimetypes
import uuid

class AWSService:
    def __init__(self):
        self.bucket_name = os.getenv('AWS_BUCKET')
        self.s3 = boto3.resource(
            "s3",
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION')
        )

    def subir_pdf(self, ruta_archivo_local, nombre_archivo):
        try:
            # Verificar si el archivo ya existe en S3
            s3_path = f"curriculums/{nombre_archivo}"
            try:
                self.s3.Object(self.bucket_name, s3_path).load()
                # Si el archivo ya existe, generar un nombre único
                base, ext = os.path.splitext(nombre_archivo)
                nombre_archivo = f"{base}_{uuid.uuid4().hex[:8]}{ext}"
                s3_path = f"curriculums/{nombre_archivo}"
                current_app.logger.warning(f"Archivo {nombre_archivo} ya existe, generado nuevo nombre: {s3_path}")
            except ClientError as e:
                if e.response['Error']['Code'] != '404':
                    raise  # Re-lanzar si el error no es "no encontrado"

            # Determinar el ContentType según la extensión del archivo
            extension = os.path.splitext(ruta_archivo_local)[1].lower()
            content_type, _ = mimetypes.guess_type(ruta_archivo_local)
            if content_type is None:
                content_type = 'application/octet-stream'  # Valor por defecto si no se detecta

            with open(ruta_archivo_local, "rb") as archivo:
                data = archivo.read()
                self.s3.Bucket(self.bucket_name).put_object(
                    Key=s3_path,
                    Body=data,
                    ContentType=content_type,
                    ContentDisposition='inline'
                )
                url = f"https://{self.bucket_name}.s3.{os.getenv('AWS_REGION')}.amazonaws.com/{s3_path}"
                current_app.logger.info(f"✅ Archivo subido a S3: {url}")
                return url, nombre_archivo  # Devolver la URL y el nombre del archivo (potencialmente modificado)
        except FileNotFoundError:
            current_app.logger.error("❌ Archivo no encontrado.")
            return None, nombre_archivo
        except ClientError as e:
            current_app.logger.error(f"❌ Error al subir a S3: {e.response['Error']['Message']}")
            return None, nombre_archivo
        except Exception as e:
            current_app.logger.error(f"❌ Error inesperado en subida a S3: {str(e)}")
            return None, nombre_archivo

    def get_file_url(self, s3_path):
        try:
            url = f"https://{self.bucket_name}.s3.{os.getenv('AWS_REGION')}.amazonaws.com/{s3_path}"
            return url
        except Exception as e:
            current_app.logger.error(f"❌ Error generando URL para {s3_path}: {str(e)}")
            return None
        
    def borrar_archivo(self, s3_path):
        """
        Elimina un archivo del bucket S3 en la ruta especificada.
        
        Args:
            s3_path (str): Ruta del archivo en el bucket (e.g., 'curriculums/nombre_archivo.pdf')
        
        Returns:
            bool: True si el archivo se eliminó correctamente, False si ocurrió un error.
        """
        try:
            # Verificar si el archivo existe antes de intentar eliminarlo
            self.s3.Object(self.bucket_name, s3_path).load()
            
            # Eliminar el archivo
            self.s3.Object(self.bucket_name, s3_path).delete()
            current_app.logger.info(f"✅ Archivo eliminado de S3: {s3_path}")
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                current_app.logger.warning(f"⚠️ Archivo no encontrado en S3: {s3_path}")
            else:
                current_app.logger.error(f"❌ Error al eliminar archivo de S3: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            current_app.logger.error(f"❌ Error inesperado al eliminar archivo de S3: {str(e)}")
            return False