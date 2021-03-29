import logging
import sys
from argparse import ArgumentParser

from cytomine import Cytomine
from cytomine.models import AnnotationCollection

def get_stats_annotations(params):

     with Cytomine(host=params.cytomine_host, public_key=params.cytomine_public_key, private_key=params.cytomine_private_key, verbose=logging.INFO) as cytomine:

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

    jobs = JobCollection()
    jobs.project = params.cytomine_id_project
    jobs.fetch()

    for job in jobs:
        print(job)
    
    return None


if __name__ == '__main__':
    parser = ArgumentParser(prog="Cytomine Python client example")

    parser.add_argument('--cytomine_host', dest='cytomine_host',
                        default='viewer2.cells-ia.com', help="host de cytomine")
    parser.add_argument('--cytomine_public_key', dest='cytomine_public_key',
                        help="la public key de cytomine")
    parser.add_argument('--cytomine_private_key', dest='cytomine_private_key',
                        help="la private key de cytomine")

    parser.add_argument('--cytomine_id_project', dest='cytomine_id_project',
                        help="el proyecto actual de cytomine")
    parser.add_argument('--cytomine_id_software', dest='cytomine_id_software',
                        help="el software actual de cytomine")

    parser.add_argument('--images_to_analyze', dest='images_to_analyze', required=False,
                        help="imagenes para filtrar el algoritmo (opcional)")
   
    params, other = parser.parse_known_args(sys.argv[1:])


    #get_stats_annotations(params)

    get_results(params)