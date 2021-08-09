# Show Region Stats

Script de Cytomine para conteo de estadístidas en una región definida por una anotación. 


Desarrollado por <a href="https://github.com/GonzaloLardies">@GonzaloLardies</a> (gon.lardies.guillen@gmail.com)


Parámetros de configuración:

- **UPLOAD_JOB_NAME** --> Nombre del algoritmo de subida de resultados (Sin versión)
- **UPLOAD_JOB_IMAGE_PARAMETER_NAME** --> Nombre del parámetro de imagen en el algoritmo de subida de resultados
- **UPLOAD_JOB_FILENAME** --> Nombre del tipo de archivo del algoritmo de subida de resultados
- **UPLOAD_JOB_FILEFORMAT** --> Formato en el que se han subido los resultados
- **POSITIVE_KEY** --> Clave de detecciones positivas
- **NEGATIVE_KEY** --> Clave de detecciones negativas
- **POSITIVE_COLOR** -->  Color asociado a detecciones positivas
- **NEGATIVE_COLOR** --> Color asociado a detecciones negativas
- **HIDDEN_PROPERTY_PREFIX** --> Prefijo de ocultación de propiedades
- **HIDDEN_TERM_PREFIX** --> Prefijo de ocultación de términos
- **STATS_FILE_NAME** --> Nombre de archivo de resultados
- **STATS_FILE_TYPE**  -->  Tipo de archivo de resultados

### Diagrama de flujo del algoritmo

![Image](https://i.ibb.co/nPptX8q/diagrama-flujo-script.jpg)

### Consideraciones para desarrollos futuros

- Los archivos subidos por el algoritmo con los puntos interiores de cada anotación están en formato MultiPoint y comprimidos con el paquete 'pickle' (con el objetivo de que ocupen el menor espacio posible). Si se quiere trabajar con ellos en el futuro se puede simplemente cargar el Multipoint con el siguiente código:
```python
import pickle

# Load MultiPoint from disc
with open('./my_multipoint', "rb") as multi_file:
    loaded_multipoint = pickle.load(multi_file)
```
