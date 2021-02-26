# -*- coding: utf-8 -*-

import logging
import sys
import os
from argparse import ArgumentParser

from cytomine import Cytomine
from cytomine.models import AnnotationCollection


def run(params):
    
    # acceso a la instancia de cytomine
    with Cytomine(host=params.host, public_key=params.public_key, private_key=params.private_key, verbose=logging.INFO) as cytomine:
        
        # se define AnnotationCollection --> contiene todas las anotaciones para (id_proyecto) + (id_software)
        annotations = AnnotationCollection(id_project=params.id_project, id_software=params.id_software, 
                                           showWKT=True, showMeta=True, showGIS=True, showTerm=True)
        annotations.fetch()
        print(annotations)

        # Se itera para imprimir cada anotacion 
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

        """
        DUDA: la idea es: (?)
            - pasarle al script como argumento el id de la anotacion y sacar stats de esa anotación
            - hacerlo para todas las anotaciones dado un proyecto y un algoritmo

        """



if __name__ == '__main__':

    # parser para seleccionar los parametros
    parser = ArgumentParser(prog="Show Region Stats")

    # Parametros
    parser.add_argument('--cytomine_host', dest='host', default='viewer2.cells-ia.com', 
                        help="The Cytomine host")
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
    