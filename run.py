import logging
import shutil
import sys
import os

import cytomine
from cytomine.models import AnnotationCollection

__version__ = "1.0.8"


def get_stats_annotations(params):

    annotations = AnnotationCollection()

    annotations.project = params.cytomine_id_project

    if params.terms_to_analyze != None:
        print("Savage!")
        annotations.term = params.terms_to_analyze

    if params.images_to_analyze != None:
        annotation.image = params.images_to_analyze

    annotations.showWKT = True
    annotations.showMeta = True
    annotations.showGIS = True
    annotations.showTerm = True
    annotations.fetch()

    return annotations

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

    finally:
        logging.info("Deleting folder %s", working_path)
        shutil.rmtree(working_path, ignore_errors=True)
        logging.debug("Leaving run()")

if __name__ == '__main__':

    logging.debug("Command: %s", sys.argv)

    with cytomine.CytomineJob.from_cli(sys.argv) as cyto_job:

        run(cyto_job, cyto_job.parameters)