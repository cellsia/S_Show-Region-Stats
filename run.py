import logging
import shutil
import json
import sys
import os

import cytomine
from cytomine.models import AnnotationCollection, Job
from cytomine.models.software import JobCollection, JobParameterCollection, JobDataCollection, JobData

__version__ = "1.0.8"


def get_stats_annotations(params):

    annotations = AnnotationCollection()

    annotations.project = params.cytomine_id_project
    annotations.term = params.terms_to_analyze

    if type(params.terms_to_analyze) != "NoneType":
        annotations.term = params.terms_to_analyze

    if type(params.images_to_analyze) != "NoneType":
        annotations.image = params.images_to_analyze

    annotations.showWKT = True
    annotations.showMeta = True
    annotations.showGIS = True
    annotations.showTerm = True
    annotations.fetch()

    filtered_by_id = [annotation for annotation in annotations if (params.cytomine_id_annotation == annotation.id)]

    if (type(params.cytomine_id_annotation) != "NoneType") and (len(filtered_by_id)>0):
        return filtered_by_id
    else:
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


    finally:
        logging.info("Deleting folder %s", working_path)
        shutil.rmtree(working_path, ignore_errors=True)
        logging.debug("Leaving run()")

if __name__ == '__main__':

    logging.debug("Command: %s", sys.argv)

    with cytomine.CytomineJob.from_cli(sys.argv) as cyto_job:

        run(cyto_job, cyto_job.parameters)