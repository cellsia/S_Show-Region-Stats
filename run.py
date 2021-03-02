# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import sys
import os
import json
from argparse import ArgumentParser

from cytomine import Cytomine, CytomineJob
from cytomine.models import AnnotationCollection, JobData
from cytomine.models.software import JobDataCollection


__version__ = "1.0.0"

def checking(params):

    check = """
    -------------------- Versión de software v{} --------------------

    Parámetros introducidos:
        - host: {}
        - public_key: PUBLIC_KEY
        - private_key: PRIVATE_KEY
        - id_project: {}
        - id_software: {}
        - id_image: {}
        - id_terms: {}
        - type_of_detections: {}

    """.format(__version__, params.host, params.id_project, params.id_software, params.id_image, params.id_term, params.type)

    return print(check)


def get_annotations(params):

    with Cytomine(host=params.host, public_key=params.public_key, private_key=params.private_key, verbose=logging.INFO) as cytomine:

        annotations = AnnotationCollection()
        annotations.project = params.id_project
        annotations.showWKT = True
        annotations.showMeta = True
        annotations.showGIS = True
        annotations.showTerm = True
        annotations.fetch()


        print("""\n     -------------------- Anotaciones --------------------\n""")
        for annotation in annotations:
            print("ID: {} | Image: {} | Project: {} | Term: {} | User: {} | Area: {} | Perimeter: {} | WKT: {}".format(
                annotation.id,
                annotation.image,
                annotation.project,
                annotation.term,
                annotation.user,
                annotation.area,
                annotation.perimeter,
                annotation.location
            ))

        return annotations

def get_results(params):

    # sacar json file con resultados

    with CytomineJob(host=params.host, public_key=params.public_key, private_key=params.private_key, project_id=params.id_project,
                     software_id=params.id_software) as cytomine_job:

        job = cytomine_job.job

        results = ""

        return results



if __name__ == '__main__':

    parser = ArgumentParser(prog="Show Region Stats")
    parser.add_argument('--cytomine_host', dest='host', default='viewer2.cells-ia.com',
                        help="The Cytomine host")
    parser.add_argument('--cytomine_public_key', dest='public_key',
                        help="The Cytomine public key")
    parser.add_argument('--cytomine_private_key', dest='private_key',
                        help="The Cytomine private key")
    parser.add_argument('--cytomine_id_project', dest='id_project',
                        help="The project from which we want the annotations")
    parser.add_argument('--cytomine_id_software', dest="id_software",
                        help="The ID of the software")
    parser.add_argument('--cytomine_image', dest='id_image',
                        help="Image instance")
    parser.add_argument('--cytomine_id_term', dest='id_term',
                        help="ID term")
    parser.add_argument('--type_of_detections', dest="type",
                        help="type of detections")
    params, other = parser.parse_known_args(sys.argv[1:])

    checking(params)
    get_annotations(params)
    get_results(params)
