import numpy as np
import logging
import shutil
import json
import sys
import os

import cytomine
from cytomine import Cytomine
from cytomine.models import AnnotationCollection, PropertyCollection, Property
from cytomine.models.software import JobCollection, JobDataCollection, JobData, JobParameterCollection, Job
from cytomine.models.annotation import Annotation
from cytomine.models.ontology import TermCollection
from shapely.geometry import MultiPoint

__version__ = "1.0.7"

def get_stats_annotations(params):

    with Cytomine(host=params.cytomine_host, public_key=params.cytomine_public_key, private_key=params.cytomine_private_key, verbose=logging.INFO) as cytomine:

        annotations = AnnotationCollection()
        annotations.project = params.cytomine_id_project

        if params.terms_to_analyze != None:
            annotations.term = params.terms_to_analyze

        if params.images_to_analyze != None:
            annotations.image = params.images_to_analyze

        annotations.showWKT = True
        annotations.showMeta = True
        annotations.showGIS = True
        annotations.showTerm = True
        annotations.fetch()

        filtered_annotations = [annotation for annotation in annotations if (params.cytomine_id_annotation==annotation.id)]

        if params.cytomine_id_annotation == None:
            return annotations
        else:
            return filtered_annotations

def get_json_results(params):

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
    pol = str(polygon)[len("MULTIPOINT "):].rstrip("(").lstrip(")").split(",")
    for i in range(0, len(pol)):
        pol[i] = pol[i].rstrip(" ").lstrip(" ")
        pol[i] = pol[i].rstrip(")").lstrip("(").split(" ")
    return pol

def process_points(points):
    pts = [[p["x"],p["y"]] for p in points]
    return pts

def is_inside(point, polygon):

    print(point)
    print(polygon)

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
        inside_points_l.append([annotation.id, inside_points, result["terms"]])
        stats.update({annotation.id:annotation_dict})

    return stats, inside_points_l

def update_properties(stats):
    for id, dic in stats.items():
        prop = {}
        annotation = Annotation().fetch(id=int(id))
        for key, value in dic.items():
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

    return None

def _generate_multipoints(detections: list) -> MultiPoint:

    points = []
    for detection in detections:
        points.append((detection['x'], detection['y']))

    return MultiPoint(points=points)

def _load_multi_class_points(job: Job, image_id: str,  terms: list, detections: dict) -> None:

    annotations = AnnotationCollection()
    for idx, points in enumerate(detections.values()):

        multipoint = _generate_multipoints(points)
        annotations.append(Annotation(location=multipoint.wkt, id_image=image_id, id_terms=[terms[idx]]))

    annotations.save()
    return None

def load_multipoints(job, inside_points_l):

    for item in inside_points_l:
        annotation = Annotation().fetch(id=int(item[0]))
        image = annotation.image
        id = annotation.id
        terms = item[2].rstrip(']').lstrip('[').split(',')

        _load_multi_class_points(job, image, terms, item[1])

    return None

def run(cyto_job, parameters):

    logging.info("----- test software v%s -----", __version__)
    logging.info("Entering run(cyto_jon=%s, parameters=%s)", cyto_job, parameters)

    job = cyto_job.job
    project = cyto_job.project

    working_path = os.path.join("tmp", str(job.id))
    if not os.path.exists(working_path):
        logging.info("Creating working directory: %s", working_path)
        os.makedirs(working_path)

    try:

        job.update(progress=0, statusComment="Collect Stats annotations")
        anotaciones = get_stats_annotations(parameters)
        if len(anotaciones) == 0:
            logging.info("No se han podido obtener anotaciones para los parámetros seleccionados")
        else:
            logging.info("Stats annotations collected")

        job.update(progress=15, statusComment="Collect Json Results")
        resultados = get_json_results(parameters)
        if len(resultados) == 0:
            logging.info("No se han podido obtener resultados para los parámetros seleccionados")
        else:
            logging.info("Results collected")

        job.update(progress=30, statusComment="Calculate Stats")
        stats, inside_points_l = get_stats(anotaciones, resultados)

        if len(stats) == 0:
            logging.info("No se han podido obtener estadísticas para los parámetros seleccionados")
        else:
            logging.info("Stats collected")

        job.update(progress=60, statusComment="Generating JSON Stats File")
        output_path = os.path.join(working_path, "stats.json")
        f = open(output_path, "w+")
        json.dump(stats, f)
        f.close()

        job_data = JobData(job.id, "stats", "stats.json").save()
        job_data.upload(output_path)

        job.update(progress=65, statusComment="Generating JSON  with annotation inside points")
        for item in inside_points_l:
            output_path2 = os.path.join(working_path, "inside_points_{}.json".format(item[0]))
            f = open(output_path2, "w+")
            json.dump(item[1], f)
            f.close()

            job_data = JobData(job.id, "detections", "inside_points_{}.json".format(item[0])).save()
            job_data.upload(output_path2)

        job.update(progress=70, statusComment="Update annotation properties")
        update_properties(stats)

        job.update(progress=80, statusComment="Generate Multipoint annotations")
        load_multipoints(job, inside_points_l)

        job.update(progress=90, statusComment="Loading job data")
        # cargar las dos anotaciones generadas como Job Data

        job.update(progress=100, statusComment="Terminated")

    finally:
        logging.info("Deleting folder %s", working_path)
        shutil.rmtree(working_path, ignore_errors=True)

        logging.debug("Leaving run()")


if __name__ == '__main__':

    logging.debug("Command: %s", sys.argv)

    with cytomine.CytomineJob.from_cli(sys.argv) as cyto_job:
        run(cyto_job, cyto_job.parameters)