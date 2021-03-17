import logging
import shutil
import json
import sys
import os

import cytomine
from cytomine import Cytomine
from cytomine.models import AnnotationCollection
from cytomine.models.software import JobCollection, JobDataCollection, JobData

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

    for job_id in jobs_ids:

        jobdatacol = JobDataCollection().fetch_with_filter(key="job", value=job_id)
        for job in jobdatacol:
            jobdata = JobData().fetch(job.id)
            filename = jobdata.filename
            if "detections" in filename:
                try:
                    jobdata.download(os.path.join("tmp/", filename))

                except AttributeError:
                    continue

    temp_files = os.listdir("tmp")
    for i in range(0, len(temp_files)):
        if temp_files[i][-4:] == "json":
            filename = temp_files[i]
            id = filename[len("detection")+2:-5]
            with open("tmp/"+filename, 'r') as json_file:
                data = json.load(json_file)
                json_file.close()
            results.append({"id":id, "data":data})

    os.system("cd tmp&&rm detections*")

    return results

def _process_polygon(polygon):
    pol = polygon[8:].lstrip('((').rstrip('))').split(',')
    for i in range(0, len(pol)):
        pol[i] = pol[i].lstrip(' ').split(' ')
    return pol

def _get_stats(annotations, results):

    for annotation in annotations:
        polygon = _process_polygon(annotation.location)

        print(polygon)

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

        job.update(progress=100, statusComment="Terminated")

    finally:
        logging.info("Deleting folder %s", working_path)
        shutil.rmtree(working_path, ignore_errors=True)

        logging.debug("Leaving run()")



if __name__ == '__main__':

    logging.debug("Command: %s", sys.argv)

    with cytomine.CytomineJob.from_cli(sys.argv) as cyto_job:
        run(cyto_job, cyto_job.parameters)
