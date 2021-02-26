# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import sys
import os
from argparse import ArgumentParser

from cytomine import Cytomine
from cytomine.models import AnnotationCollection


def run(params):
    
    with Cytomine(host=params.host, public_key=params.public_key, private_key=params.private_key, verbose=logging.INFO) as cytomine:
        
        annotations = AnnotationCollection(id_project=params.id_project, id_software=params.id_software)

        annotations.showWKT = True
        annotations.showMeta = True
        annotations.showGIS = True
        annotations.showTerm = True
        annotations.fetch()

        print(annotations)


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



if __name__ == '__main__':

    # get params
    parser = ArgumentParser(prog="Show Region Stats")

    # Cytomine
    parser.add_argument('--cytomine_host', dest='host',
                        default='demo.cytomine.be', help="The Cytomine host")
    parser.add_argument('--cytomine_public_key', dest='public_key',
                        help="The Cytomine public key")
    parser.add_argument('--cytomine_private_key', dest='private_key',
                        help="The Cytomine private key")
    parser.add_argument('--cytomine_id_project', dest='id_project',
                        help="The project from which we want the annotations")
    parser.add_argument('--cytomine_id_software', dest='id_software',
                        help="The software wich we want the annotations")
    params, other = parser.parse_known_args(sys.argv[1:])
    
    run(params)
    