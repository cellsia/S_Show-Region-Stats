import numpy as np
import logging
import shutil
import json
import sys
import os

import cytomine
from cytomine import Cytomine
from cytomine.models import AnnotationCollection, PropertyCollection, Property, AlgoAnnotationTerm, Annotation, TermCollection, Term, ImageInstance, Project, UserJobCollection
from cytomine.models.software import JobCollection, JobParameterCollection, JobDataCollection, JobData, Job
from shapely.geometry import MultiPoint, Polygon
from datetime import datetime

__version__ = "1.2.4"


def get_stats_annotations(params): # funcion para sacar las anotaciones manuales "Stats"

    annotations = AnnotationCollection()

    # filtramos todas las anotaciones manuales del proyecto que tengan el termino "Stats"
    annotations.project = params.cytomine_id_project
    annotations.term = "Stats"

    # si se especifica alguna imagen, filtramos por imagen
    if type(params.images_to_analyze) != "NoneType":
        annotations.image = params.images_to_analyze

    annotations.showWKT = True
    annotations.showMeta = True
    annotations.showGIS = True
    annotations.showTerm = True
    annotations.fetch()

    # devolvemos anotaciones
    return annotations


get_new_delta = lambda n, a, b: (b - a) / n # calcular aumento delta para barra de progreso

def get_results(params, job): # funcion para cargar los resultados a partir de los arhivos .json cargados. 

    results = [] # array con resultados 
    equiv = {} # diccionario de equivalencias (filename - cytomine_image_term_id)
    delta = 5 # actualizar barra de progreso

    # sacamos lista con todos los job id's
    jobs = JobCollection()
    jobs.project = params.cytomine_id_project
    jobs.fetch()
    jobs_ids = [j.id for j in jobs if (j.name[:17] != "Show Region Stats")]


    for job_id in jobs_ids:

        # para cada job sacamos prametros y coleccion de datos
        jobparamscol = JobParameterCollection().fetch_with_filter(key="job", value=job_id)
        jobdatacol = JobDataCollection().fetch_with_filter(key="job", value=job_id)

        for _job in jobdatacol:

            jobdata = JobData().fetch(_job.id)
            filename = jobdata.filename

            allowed_params = ["cytomine_image", "cytomine_id_image", "cytomine_image_instance"]
            [equiv.update({filename:int(param.value)}) for param in jobparamscol if (str(param).split(" : ")[1] in allowed_params) ]

            # si el .json tiene "detections en el nombre de archivo lo descargamos y lo metemos en la carpeta tmp/"
            if "detections" in filename:
                try:
                    jobdata.download(os.path.join("tmp/", filename))
                except AttributeError:
                    continue


        delta += get_new_delta(len(jobs_ids), 5, 20)
        job.update(progress=int(delta), statusComment="Recogiendo resultados")        

    # cargamos los resultados a partir de los archivos que hemos descargado
    temp_files = os.listdir("tmp")
    for i in range(0, len(temp_files)):
        if temp_files[i][-4:] == "json":
            filename = temp_files[i]
            try:
                image = equiv[filename] # recuperamos la imagen a la que hace refereancia cada archivo bassandonos en el dic de equivalencias
                with open("tmp/"+filename, 'r') as json_file:
                    data = json.load(json_file)
                    json_file.close()
                results.append({"image":image,"data":data}) # añadimos el resultado con su imagen asociada
            except KeyError:
                continue

    os.system("cd tmp&&rm detections*") # eliminamos archivos temporales

    # devolvemos resultados
    return results

def process_polygon(polygon): # funcion que procesa .location de anotacion manual para generar poligono shapely
    pol = str(polygon)[7:].rstrip("(").lstrip(")").split(",")
    for i in range(0, len(pol)):
        pol[i] = pol[i].rstrip(" ").lstrip(" ")
        pol[i] = pol[i].rstrip(")").lstrip("(").split(" ")
        pol[i][0] = float(pol[i][0])
        pol[i][1] = float(pol[i][1])
        pol[i] = tuple(pol[i])
    return pol

def process_points(points): # funcion que procesa los puntos de cada termino para generar un MultiPoint shapely
    pts = [[p["x"],p["y"]] for p in points]
    return pts

def get_stats(annotations, results, job): # funcion que calcula las estadísticas

    stats = {} # diccionario con estadisticas
    inside_points_l = [] # array que va a contener los puntos de dentro de cada anotacion (+ items)
    delta = 20 

    for annotation in annotations: # iteramos sobre cada anotación
        annotation_dict, inside_points = {}, {}
        polygon = Polygon(process_polygon(annotation.location))
        
        for result in results: # seleccionamos el resultado correspondiente a la imagen de la anotación
            if result["image"] == annotation.image:

                # informacion general de la imagen 
                all_points = result["data"]
                image_info, global_cter = {}, 0
                for key, value in all_points.items():
                    count = len(value)
                    global_cter+=count
                    image_info.update({"conteo_{}_imagen".format(key):count})
                image_info.update({"conteo_total_imagen":global_cter})
                image_info.update({"area_anotacion":annotation.area})
                image_info.update({"imagen_anotacion":annotation.image})
                annotation_dict.update({"info_imagen":image_info})

                # informacion de cada termino
                for key, value in all_points.items():
                    pts = MultiPoint(process_points(value))
                    ins_pts = [p for p in pts if polygon.contains(p)]
                    cter = len(ins_pts)
                    ins_p = []
                    [ins_p.append({"x":p.x, "y":p.y}) for p in ins_pts]
                    inside_points.update({key:ins_p})
                    particular_info ={
                        "conteo_{}_anotacion".format(key):cter,
                        "densidad_{}_anotacion(n/micron²)".format(key):cter/annotation.area
                    }
                    annotation_dict.update({"info_termino_{}".format(key):particular_info})
        inside_points_l.append([annotation.id, inside_points]) # guardamos los puntos de dentro para trabajar con ellos posteriormente
        stats.update({annotation.id:annotation_dict}) # atualizamos el diccionario de stats
        
        # barra de progres
        delta += get_new_delta(len(annotations), 20, 60)
        job.update(progress=int(delta), statusComment="Calculando estadísticas")

    # devolvemos estadísticas y puntos de dentro de las anotaciones
    return stats, inside_points_l

def update_properties(stats, job): # funcion que actualiza propiedades de imagen y anotaciones manuales
    delta = 75
    for id, dic in stats.items():
        prop, prop2 = {}, {} # prop contiene las propiedades de la anotacion  y prop2 las de la imagen
        annotation = Annotation().fetch(id=int(id)) # anotacion para cambiar sus prop
        for key, value in dic.items():
            if key == "info_imagen":
                img_id = value["imagen_anotacion"]
                image = ImageInstance().fetch(id=int(img_id)) # imagen para cambiar sus prop
                for key2, value2 in value.items():
                    prop2.update({key2:value2})
            else:
                for key2, value2 in value.items():
                    prop.update({key2:value2})

        for k, v in prop.items():
            current_properties = PropertyCollection(annotation).fetch()
            current_property = next((p for p in current_properties if p.key == k), None)
            
            if current_property:
                current_property.fetch()
                current_property.value = v 
                current_property.update()
            else:
                Property(annotation, key=k, value=v).save()
        Property(annotation, key="ID", value=int(id)).save()

        for k, v in prop2.items():
            current_properties = PropertyCollection(image).fetch()
            current_property = next((p for p in current_properties if p.key == k), None)
            
            if current_property:
                current_property.fetch()
                current_property.value = v 
                current_property.update()
            else:
                Property(image, key=k, value=v).save()

        delta += get_new_delta(len(stats), 75, 85)
        job.update(progress=int(delta), statusComment="Actualizando propiedades de las anotaciones Stats")

    return None

def _generate_multipoints(detections: list) -> MultiPoint:

    points = []
    for detection in detections:
        points.append((detection['x'], detection['y']))

    return MultiPoint(points=points)

def _load_multi_class_points(job: Job, image_id: str, detections: dict, id_: int, params, hour, date, mantener_ids) -> None:

    terms = [key for key,value in detections.items()]

    
    project = Project().fetch(params.cytomine_id_project)
    termscol = TermCollection().fetch_with_filter("project", project.id)
    

    for idx, points in enumerate(detections.values()):

        term_name = "INSIDE_POINTS_{}_ANOTACION_{}_FECHA_{}_{}".format(terms[idx],id_, date, hour)

        multipoint = _generate_multipoints(points)
        
        term1 = Term(term_name, project.ontology, "F44E3B").save()
        termscol = TermCollection().fetch_with_filter("project", project.id)
            
        t1 = [t.id for t in termscol if t.name == term_name]
        mantener_ids.append(t1[0])
        
        annotations = AnnotationCollection()
        annotations.append(Annotation(location=multipoint.wkt, id_image=image_id, id_project=params.cytomine_id_project, id_terms=t1))
        annotations.save()
        
        """userjobs = UserJobCollection()
        userjobs.fetch_with_filter("project", params.cytomine_id_project)
        userjobs_ids = [userjob.id for userjob in userjobs]

        detections = AnnotationCollection()
        detections.project = params.cytomine_id_project
        detections.users = userjobs_ids
        detections.term = t1
        detections.fetch()

        anot_id = detections[0].id
        AlgoAnnotationTerm(id_annotation=anot_id, id_term=t1[0], id_expected_term=t1[0]).save()"""
        

    return None

def delete_results(params, lista_id, job):

    users = UserJobCollection().fetch_with_filter("project", params.cytomine_id_project)
    ids = [user.id for user in users]
    delta = 95

    annotations = AnnotationCollection()
    annotations.project = params.cytomine_id_project
    annotations.users = ids
    annotations.showTerm = True
    annotations.fetch()
    
    
    cyto_job.open_admin_session()
    ids_to_delete = [annotation.id for annotation in annotations if not (annotation.term[0] in lista_id)]
    
    with Cytomine(host=params.cytomine_host, public_key=params.cytomine_public_key, private_key=params.cytomine_private_key, verbose=logging.INFO) as cytomine:
        cytomine.open_admin_session()
        [Annotation().delete(id=id_) for id_ in ids_to_delete]
        
        
        project = Project().fetch(params.cytomine_id_project)
        termscol = TermCollection().fetch_with_filter("project", project.id)
        ids_to_delete = [t.id for t in termscol if (t.name != "Stats" and not (t.id in lista_id))]

        for id_ in ids_to_delete:
            Term().delete(id=id_)
            delta += get_new_delta(len(ids_to_delete), 95, 100)
            job.update(progress=int(delta), statusComment="Borrando reultados anteriores")

    return None

def run(cyto_job, parameters): # funcion principal del script - maneja el flujo del algoritmo

    # control de version y parametros
    logging.info("----- test software v%s -----", __version__)
    logging.info("Entering run(cyto_job=%s, parameters=%s)", cyto_job, parameters)

    job = cyto_job.job
    project = cyto_job.project

    # creamos carpeta para guardar archivos temporales 
    working_path = os.path.join("tmp", str(job.id))
    if not os.path.exists(working_path):
        logging.info("Creating working directory: %s", working_path)
        os.makedirs(working_path)

    try:
        
        # recoger anotaciones manuales "Stats"
        job.update(progress=0, statusComment="Recogiendo anotaciones manuales con el término 'Stats'")
        anotaciones = get_stats_annotations(parameters)
         
        if len(anotaciones) == 0: # terminamos Job si no hay (o no se pueden recuperar) anotaciones manuales
            job.update(progress=100, status=Job.FAILED, statusComment="No se han podido encontrar anotaciones manuales con el término 'Stats'")

        # recoger resultados
        job.update(progress=5, statusComment="Recogiendo resultados")
        resultados = get_results(parameters, job)

        if len(resultados) == 0: # terminamos Job si no hay (o no se pueden recuperar) resultados
            job.update(progress=100, status=Job.FAILED, statusComment="No se han podido encontrar resultados")


        # calcular estadisticas
        job.update(progress=20, statusComment="Calculando estadísticas")
        stats, inside_points_l = get_stats(anotaciones, resultados, job)

        if len(stats) == 0: # terminamos Job si no se han podido calcular las estadísticas
            job.update(progress=100, status=Job.FAILED, statusComment="No se han podido calcular las estadísticas!")

        # generamos archivos con los resultados
        job.update(progress=60, statusComment="Generando archivo .JSON con las estadísticas")

        output_path = os.path.join(working_path, "stats.json")
        f = open(output_path, "w+")
        json.dump(stats, f)
        f.close()

        job_data = JobData(job.id, "stats", "stats.json").save()
        job_data.upload(output_path)

        job.update(progress=65, statusComment="Generando archivos .JSON con los puntos de dentro de la(s) anotación(es)")
        delta = 65
        for item in inside_points_l:

            output_path2 = os.path.join(working_path, "inside_points_{}.json".format(item[0]))
            f = open(output_path2, "w+")
            json.dump(item[1], f)
            f.close()

            job_data = JobData(job.id, "detections", "inside_points_{}.json".format(item[0])).save()
            job_data.upload(output_path2)

            delta += get_new_delta(len(inside_points_l), 65, 75)
            job.update(progress=int(delta), statusComment="Generando archivos .JSON con los puntos de dentro de la(s) anotación(es)")

        # actualizamos propiedades de anotaciones manuales e imagen
        job.update(progress=75, statusComment="Actualizando propiedades de las anotaciones Stats")
        update_properties(stats, job)

        # subimos las anotaciones MultiPoint como detecciones
        job.update(progress=85, statusComment="Subiendo detecciones con los puntos de la anotación")
        delta = 85

        time = datetime.now()
        hour = time.strftime('%H:%M')
        date = time.strftime('%d-%m-%Y')

        mantener_ids = []
        
        for item in inside_points_l:
            annotation = Annotation().fetch(id=int(item[0]))
            id_ = int(item[0])
            image_id = annotation.image
            detections = item[1]

            boolean = True
            for key, value in detections.items():
                if len(value) == 0:
                    boolean = False

            if boolean:
                _load_multi_class_points(job, image_id, item[1], id_, parameters, hour, date, mantener_ids)
            else:
                continue

            delta += get_new_delta(len(inside_points_l), 85, 95)
            job.update(progress=int(delta), statusComment="Subiendo detecciones con los puntos de la anotación")

        if parameters.clear_results == True:
            delete_results(parameters, mantener_ids, job)

        job.update(progress=100, statusComment="Terminado")
        

    finally:
        # borramos archivos temporales antes de finalizar
        logging.info("Deleting folder %s", working_path)
        shutil.rmtree(working_path, ignore_errors=True)
        logging.debug("Leaving run()")

if __name__ == '__main__':

    logging.debug("Command: %s", sys.argv)

    # esatblecemos conexion con el host y creamos un nuevo Job
    with cytomine.CytomineJob.from_cli(sys.argv) as cyto_job:

        # funcion principal del script
        run(cyto_job, cyto_job.parameters)