import logging
import shutil
import json
import sys
import os

import cytomine
from cytomine import Cytomine
from cytomine.models import AnnotationCollection
from cytomine.models.software import JobCollection, JobDataCollection, JobData, JobParameterCollection, JobParameter

__version__ = "1.0.6"

def _get_stats_annotations(params):

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

def _get_json_results(params):

    results = []

    jobs = JobCollection()
    jobs.project = params.cytomine_id_project
    jobs.fetch()
    jobs_ids = [job.id for job in jobs]
    equiv = {}

    for job_id in jobs_ids:

        jobparamscol = JobParameterCollection().fetch_with_filter(key="job", value=job_id)
        jobdatacol = JobDataCollection().fetch_with_filter(key="job", value=job_id)

        for job in jobdatacol:

            jobdata = JobData().fetch(job.id)
            filename = jobdata.filename

            for param in jobparamscol:
                if str(param).split(" : ")[1] in ["cytomine_image"]:
                    equiv.update({filename:int(param.value)})

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
                with open("tmp/"+filename, 'r') as json_file:
                    data = json.load(json_file)
                    json_file.close()
                results.append({"image":image, "data":data})
            except KeyError:
                continue

    os.system("cd tmp&&rm detections*")

    return results

def _process_polygon(polygon):
    pol = polygon[8:].lstrip('((').rstrip('))').split(',')
    for i in range(0, len(pol)):
        pol[i] = pol[i].lstrip(' ').split(' ')
    return pol

def _get_stats(annotations, results):

    stats = {}

    for annotation in annotations:

        annotation_dict = {}
        polygon = _process_polygon(annotation.location)

        for result in results:
            if result["image"] == annotation.image:

                points = result["data"]
                image_info, global_cter = {}, 0
                for key, value in points.items():
                    count = len(points[key])
                    global_cter+=count
                    image_info.update({"conteo_[{}]".format(key):count})

                image_info.update({"global_counter":global_cter})
                annotation_dict.update({"image_info":image_info})

        stats.update({annotation.id:annotation_dict})

    print(stats)
    return stats

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
        anotaciones = _get_stats_annotations(parameters)
        if len(anotaciones) == 0:
            logging.info("No se han podido obtener anotaciones para los parámetros seleccionados")
        else:
            logging.info("Stats annotations collected")

        job.update(progress=15, statusComment="Collect Json Results")
        resultados = _get_json_results(parameters)
        if len(resultados) == 0:
            logging.info("No se han podido obtener resultados para los parámetros seleccionados")
        else:
            logging.info("Results collected")

        job.update(progress=30, statusComment="Calculate Stats")
        stats = _get_stats(anotaciones, resultados)
        anotaciones, resultados = None, None
        if len(stats) == 0:
            logging.info("No se han podido obtener estadísticas para los parámetros seleccionados")
        else:
            logging.info("Stats collected")

        job.update(progress=60, statusComment="Updating Annotaion Properties")

        job.update(progress=100, statusComment="Terminated")

    finally:
        logging.info("Deleting folder %s", working_path)
        shutil.rmtree(working_path, ignore_errors=True)

        logging.debug("Leaving run()")



if __name__ == '__main__':

    logging.debug("Command: %s", sys.argv)

    with cytomine.CytomineJob.from_cli(sys.argv) as cyto_job:
        run(cyto_job, cyto_job.parameters)
