import numpy as np
import logging
import shutil
import json
import sys
import os

import cytomine
from cytomine.models import AnnotationCollection, PropertyCollection, Property, AnnotationTerm, Annotation, TermCollection, Term, ImageInstance, Project
from cytomine.models.software import JobCollection, JobParameterCollection, JobDataCollection, JobData, Job
from shapely.geometry import MultiPoint

__version__ = "1.0.8"


def get_stats_annotations(params):

    annotations = AnnotationCollection()

    annotations.project = params.cytomine_id_project
    annotations.term = "Stats"

    if type(params.images_to_analyze) != "NoneType":
        annotations.image = params.images_to_analyze

    annotations.showWKT = True
    annotations.showMeta = True
    annotations.showGIS = True
    annotations.showTerm = True
    annotations.fetch()

    return annotations

def get_results(params):

    results = []
    equiv, equiv2 = {}, {}

    jobs = JobCollection()
    jobs.project = params.cytomine_id_project
    jobs.fetch()
    jobs_ids = [job.id for job in jobs]

    for job_id in jobs_ids:

        jobparamscol = JobParameterCollection().fetch_with_filter(key="job", value=job_id)
        jobdatacol = JobDataCollection().fetch_with_filter(key="job", value=job_id)

        for job in jobdatacol:

            jobdata = JobData().fetch(job.id)
            filename = jobdata.filename

            for param in jobparamscol:
                if str(param).split(" : ")[1] in ["cytomine_image"]:
                    equiv.update({filename:int(param.value)})
                if str(param).split(" : ")[1] in ["cytomine_id_term"]:
                    equiv2.update({filename:param.value})

            if "detections" in filename:
                try:
                    jobdata.download(os.path.join("tmp/", filename))
                except AttributeError:
                    continue

    temp_files = os.listdir("tmp")
    for i in range(0, len(temp_files)):
        if temp_files[i][-4:] == "json":
            filename = temp_files[i]
            try:
                image = equiv[filename]
                terms = equiv2[filename]
                with open("tmp/"+filename, 'r') as json_file:
                    data = json.load(json_file)
                    json_file.close()
                results.append({"image":image, "terms":terms ,"data":data})
            except KeyError:
                continue

    os.system("cd tmp&&rm detections*")

    return results

def process_polygon(polygon):
    pol = str(polygon)[7:].rstrip("(").lstrip(")").split(",")
    for i in range(0, len(pol)):
        pol[i] = pol[i].rstrip(" ").lstrip(" ")
        pol[i] = pol[i].rstrip(")").lstrip("(").split(" ")
    return pol

def process_points(points):
    pts = [[p["x"],p["y"]] for p in points]
    return pts

def is_inside(point, polygon):

    v_list = []
    for vert in polygon:
        vector = [0,0]
        vector[0] = float(vert[0]) - float(point[0])
        vector[1] = float(vert[1]) - float(point[1])
        v_list.append(vector)

    v_list.append(v_list[0])

    angle = 0
    for i in range(0, len(v_list)-1):
        v1 = v_list[i]
        v2 = v_list[i+1]
        unit_v1 = v1 / np.linalg.norm(v1)
        unit_v2 = v2 / np.linalg.norm(v2)
        dot_prod = np.dot(unit_v1, unit_v2)
        angle += np.arccos(dot_prod)

    if round(angle, 4) == 6.2832:
        return True
    else:
        return False

def get_stats(annotations, results):

    stats = {}
    inside_points_l = []

    for annotation in annotations:
        annotation_dict, inside_points = {}, {}
        polygon = process_polygon(annotation.location)

        for result in results:
            if result["image"] == annotation.image:

                points = result["data"]
                image_info, global_cter = {}, 0
                for key, value in points.items():
                    count = len(value)
                    global_cter+=count
                    image_info.update({"conteo_{}_imagen".format(key):count})

                image_info.update({"conteo_total_imagen":global_cter})
                image_info.update({"area_anotacion":annotation.area})
                image_info.update({"imagen_anotacion":annotation.image})
                annotation_dict.update({"info_imagen":image_info})

                for key, value in points.items():
                    ins_p = []
                    pts = process_points(value)
                    cter = 0
                    for p in pts:
                        if is_inside(p, polygon):
                            ins_p.append({"x":p[0], "y":p[1]})
                            cter+=1
                    inside_points.update({key:ins_p})
                    particular_info ={
                        "conteo_{}_anotacion".format(key):cter,
                        "densidad_{}_anotación(n/micron²)".format(key):cter/annotation.area
                    }
                    annotation_dict.update({"info_termino_{}".format(key):particular_info})
        inside_points_l.append([annotation.id, inside_points])
        stats.update({annotation.id:annotation_dict})

    return stats, inside_points_l

def update_properties(stats):
    for id, dic in stats.items():
        prop, prop2 = {}, {}
        annotation = Annotation().fetch(id=int(id))
        for key, value in dic.items():
            if key == "info_imagen":
                img_id = value["imagen_anotacion"]
                image = ImageInstance().fetch(id=int(img_id))
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

    return None

def _generate_multipoints(detections: list) -> MultiPoint:

    points = []
    for detection in detections:
        points.append((detection['x'], detection['y']))

    return MultiPoint(points=points)

def _load_multi_class_points(job: Job, image_id: str, detections: dict, id_: int, params) -> None:

    terms = [key for key,value in detections.items()]

    termscol = TermCollection().fetch_with_filter("project", params.cytomine_id_project)
    project = Project().fetch(params.cytomine_id_project)
    

    for idx, points in enumerate(detections.values()):

        term_name = "INSIDE_POINTS_{}_ANOT_{}".format(terms[idx], id_)

        multipoint = _generate_multipoints(points)
        

        l = [t.name for t in termscol]
        termscol = TermCollection().fetch_with_filter("project", params.cytomine_id_project)
        t1 = [t.id for t in termscol if t.name == term_name]
        
        if not(term_name in l):
            term1 = Term(term_name, project.ontology, "F44E3B").save()
        annotation = Annotation(location=multipoint.wkt, id_image=image_id, id_project=params.cytomine_id_project, id_terms=t1).save()        
        
    return None

def run(cyto_job, parameters):

    logging.info("----- test software v%s -----", __version__)
    logging.info("Entering run(cyto_job=%s, parameters=%s)", cyto_job, parameters)

    job = cyto_job.job
    project = cyto_job.project

    working_path = os.path.join("tmp", str(job.id))
    if not os.path.exists(working_path):
        logging.info("Creating working directory: %s", working_path)
        os.makedirs(working_path)

    try:

        job.update(progress=0, statusComment="Recogiendo anotaciones Stats")
        anotaciones = get_stats_annotations(parameters)
        
        if len(anotaciones) == 0:
            job.update(progress=100, status=Job.FAILED, statusComment="No se han podido encontrar anotaciones stats!")

        job.update(progress=15, statusComment="Recogiendo resultados")
        resultados = get_results(parameters)

        if len(resultados) == 0:
            job.update(progress=100, status=Job.FAILED, statusComment="No se han podido encontrar resultados para las anotaciones dadas!")

        job.update(progress=30, statusComment="Calculando estadísticas")
        stats, inside_points_l = get_stats(anotaciones, resultados)

        if len(stats) == 0:
            job.update(progress=100, status=Job.FAILED, statusComment="No se han podido calcular las estadísticas!")

        job.update(progress=60, statusComment="Generando archivo .JSON con los resultados")
        output_path = os.path.join(working_path, "stats.json")
        f = open(output_path, "w+")
        json.dump(stats, f)
        f.close()

        job_data = JobData(job.id, "stats", "stats.json").save()
        job_data.upload(output_path)

        job.update(progress=65, statusComment="Generando archivos .JSON con los puntos de dentro de la(s) anotación(es)")
        for item in inside_points_l:
            output_path2 = os.path.join(working_path, "inside_points_{}.json".format(item[0]))
            f = open(output_path2, "w+")
            json.dump(item[1], f)
            f.close()

            job_data = JobData(job.id, "detections", "inside_points_{}.json".format(item[0])).save()
            job_data.upload(output_path2)
            
        job.update(progress=70, statusComment="Actualizando propiedades de las anotaciones Stats")
        update_properties(stats)

        job.update(progress=80, statusComment="Subiendo anotaciones manuales con los puntos de la anotación")
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
                _load_multi_class_points(job, image_id, item[1], id_, parameters)
            else:
                continue
        

    finally:
        logging.info("Deleting folder %s", working_path)
        shutil.rmtree(working_path, ignore_errors=True)
        logging.debug("Leaving run()")

if __name__ == '__main__':

    logging.debug("Command: %s", sys.argv)

    with cytomine.CytomineJob.from_cli(sys.argv) as cyto_job:

        run(cyto_job, cyto_job.parameters)