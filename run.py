import logging
import shutil
import sys
import os

import cytomine
from cytomine import Cytomine
from cytomine.models import AnnotationCollection, UserJobCollection, JobData

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

    userjobs = UserJobCollection()
    userjobs.fetch_with_filter("project", params.cytomine_id_project)
    userjobs_l = [userjob.id for userjob in userjobs]

    
    filename =  'detections-' + str(job_id) + '.json'
    jobdata = JobData()
    jobdata.id = userjobs_l
    jobdata.fetch()
    print(jobdata)
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
        annotations = _get_stats_annotations(parameters)
        if len(annotations) == 0:
            logging.info("No se han podido obtener anotaciones con los parámetros seleccionados")
        else:
            logging.info("Stats annotations collected")
            

        job.update(progress=15, statusComment="Collect Json Results")
        results = _get_json_results(parameters)


        job.update(progress=100, statusComment="Terminated")
    
    finally:
        logging.info("Deleting folder %s", working_path)
        shutil.rmtree(working_path, ignore_errors=True)

        logging.debug("Leaving run()")



if __name__ == '__main__':

    logging.debug("Command: %s", sys.argv)

    with cytomine.CytomineJob.from_cli(sys.argv) as cyto_job:
        run(cyto_job, cyto_job.parameters)