# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import sys
import os
import json
import numpy as np
import csv
import shutil

import cytomine
from cytomine import Cytomine
from cytomine.models import AnnotationCollection, UserJobCollection, Property, Annotation, AttachedFile, JobData, Term


__version__ = "1.0.2"

def process_polygon(polygon):
    pol = polygon[8:].lstrip('((').rstrip('))').split(',')
    for i in range(0, len(pol)):
        pol[i] = pol[i].lstrip(' ').split(' ')
    return pol

def process_points(points):
    pts = points[11:].lstrip('(').rstrip(')').split(',')
    for i in range(0, len(pts)):
        pts[i] = pts[i].lstrip(' (').rstrip(')').split(' ')
    return pts


def is_inside(point, polygon):

    v_list = []
    for vert in polygon:
        vector = [0,0]
        vector[0] = float(vert[0]) - float(point[0])
        vector[1] = float(vert[1]) - float(point[1])
        v_list.append(vector)

    # se vuelve a introducir el primer vector para calcular ángulos
    v_list.append(v_list[0])

    angle = 0
    for i in range(0, len(v_list)-1):
        v1 = v_list[i]
        v2 = v_list[i+1]
        unit_v1 = v1 / np.linalg.norm(v1)
        unit_v2 = v2 / np.linalg.norm(v2)
        dot_prod = np.dot(unit_v1, unit_v2)
        angle += np.arccos(dot_prod)


    if round(angle,4) == 6.2832:
        return True
    else:
        return False

def get_term_name(term_id, params):

    with Cytomine(host=params.cytomine_host, public_key=params.cytomine_public_key, private_key=params.cytomine_private_key, verbose=logging.INFO) as cytomine:
        
        term_str = str(term_id)
        term = term_str.rstrip("]").lstrip("[")
        term = Term().fetch(id=term_id)
        return term.name

def get_stats_annotations(params):

    with Cytomine(host=params.cytomine_host, public_key=params.cytomine_public_key, private_key=params.cytomine_private_key, verbose=logging.INFO) as cytomine:

        print("""\n     -------------------- Annotations Stats --------------------\n""")

        annotations = AnnotationCollection()
        annotations.project = params.cytomine_id_project

        # Busqueda o bien por ID de anotación o bien por término
        if not(params.cytomine_id_annotation == None):
            annotations.id = params.cytomine_id_annotation
        else:
            annotations.term = params.terms_to_analyze

        # Se especifica imagen o se busca en todas
        if not(params.images_to_analyze == None):
            annotations.images = params.images_to_analyze

        annotations.showWKT = True
        annotations.showMeta = True
        annotations.showGIS = True
        annotations.showTerm = True
        annotations.fetch()

        for annotation in annotations:
            print("ID: {} | Image: {} | Project: {} | User: {} | Term: {} | Area: {} | Perimeter: {} | WKT: Polygon".format(
                annotation.id,
                annotation.image,
                annotation.project,
                annotation.user,
                annotation.term,
                annotation.area,
                annotation.perimeter,
                # annotation.location
            ))

        if len(annotations) == 0:
            print("No se han encontrado anotaciones para los parámetros dados")

        return annotations


def get_results(params):

        print("""\n     ------------------------ UserJobs -------------------------\n""")

        userjobs = UserJobCollection()
        userjobs.fetch_with_filter("project", params.cytomine_id_project)

        userjobs_l = []
        [userjobs_l.append(userjob.id) for userjob in userjobs];
        print(userjobs_l)


        print("""\n     ------------------------- Results -------------------------\n""")

        results = AnnotationCollection()

        # O búsqueda de imagen o todas
        if not(params.images_to_analyze == None):
            results.image = params.images_to_analyze
        else:
            results.project = params.cytomine_id_project

        results.users= userjobs_l
        results.showWKT = True
        results.showMeta = True
        results.showGIS = True
        results.showTerm = True
        results.fetch()

        for result in results:
            print("ID: {} | Image: {} | Project: {} | Term: {} | User: {} | WKT: MultiPoint".format(
                result.id,
                result.image,
                result.project,
                result.term,
                result.user,
                # result.location
            ))

        if len(results) == 0:
            print("No se han encontrado resultados para los parámetros dados")

        return results

def get_stats(annotations, results):

    print("""\n     -------------------------- Stats --------------------------\n""")

    stats = []
    for annotation in annotations:

        polygon = process_polygon(annotation.location)
        annotation_dict = {}
        global_cter, global_image_cter = 0, 0

        for result in results:
            if result.image == annotation.image:

                points = process_points(result.location)

                # conteo de puntos dentro de la anotación
                cter = 0
                for point in points:
                    if is_inside(point, polygon):
                        cter += 1
                    else:
                        continue

                global_cter += cter
                global_image_cter += len(points)
                result_dict = {
                    "count": cter,
                    "global_image_count": len(points)
                }
                annotation_dict.update({str(result.term): result_dict})
            else:
                continue

        general_dict = {
            "annotation_id": annotation.id,
            "annotation_term": annotation.term,
            "annotation_image": annotation.image,
            "annotation_project": annotation.project,
            "annotation_area": annotation.area,
            "global_cter": global_cter,
            "global_image_cter": global_image_cter
        }
        annotation_dict.update({"general_info": general_dict})
        stats.append(annotation_dict)

    print(stats)
    if len(stats) == 0:
        print("No se han podido calcular las estadísticas con los parámetros dados")

    return stats

def load_annotation_properties(stats, params):

    print("""\n     ---------------------- Adding  props ----------------------\n""")

    with Cytomine(host=params.cytomine_host, public_key=params.cytomine_public_key, private_key=params.cytomine_private_key, verbose=logging.INFO) as cytomine:

        for stat in stats:

            ID = stat["general_info"]["annotation_id"]
            global_counter = stat["general_info"]["global_cter"]
            global_image_counter = stat["general_info"]["global_image_cter"]
            anot_area = stat["general_info"]["annotation_area"]

            annotation = Annotation().fetch(id=ID)
            Property(annotation, key='Detections_annotation', value=global_counter).save()
            Property(annotation, key='Detections_image', value=global_image_counter).save()

            for key, value in stat.items():
                if key != "general_info":
                    Property(annotation, key="Detections_term"+get_term_name(key, params)+"_annotation", value=value["count"]).save()
                    Property(annotation, key="Detections_term"+get_term_name(key, params)+"_image", value=value["global_image_count"]).save()

        return print("Done")

def generate_rows(stats):

    print("""\n     ------------------- Generating CSV file -------------------\n""")

    rows = []
    for stat in stats:

        ID = stat["general_info"]["annotation_id"]
        global_cter = stat["general_info"]["global_cter"]
        global_image_cter = stat["general_info"]["global_image_cter"]
        anot_area = stat["general_info"]["annotation_area"]

        rows.append([">>>>>>>>>>>>>>>>>>>>>>>>> General info Annotation: {} <<<<<<<<<<<<<<<<<<<<<<<<<".format(ID)])
        rows.append(["Global counter", global_cter])
        rows.append(["Global_image_counter", global_image_cter])
        rows.append(["Annotation_area", anot_area])
        rows.append([])

        for key, value in stat.items():
            if key != "general_info":
                rows.append(["---------- Term: {} ----------".format(get_term_name(key, params))])
                for k, v in value.items():
                    rows.append([k, v])

        rows.append([])

    return rows

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

        # Sacar las anotaciones Stats con las regiones de interés
        job.update(progress=0, statusComment="Getting stats annotations")
        annotations = get_stats_annotations(parameters)
        logging.info("Finished getting stats annotations")

        # Sacar nubes de puntos de las imagenes con anotaciones
        job.update(progress=15, statusComment="Getting Multipoint Results")
        results = get_results(parameters)
        logging.info("Finished getting multipoint results")

        # Sacar estadísticas de cada anotación
        job.update(progress=30, statusComment="calculating Stats")
        stats = get_stats(annotations, results)
        logging.info("Finished calculating stats")

         # Cargar los resultados en propiedades de la anotación formato clave-valor
        job.update(progress=80, statusComment="Posting annotation properties")
        load_annotation_properties(stats, parameters)
        logging.info("Finished posting annotation properties")

        # Generar archivo stats.csv
        job.update(progress=90, statusComment="Generating .CSV file")
        rows = generate_rows(stats)

        
        output_path = os.path.join(working_path, "stats.csv")
        f= open(output_path,"w+")
        writer = csv.writer(f)
        writer.writerows(rows)
        f.close() 

        
        job_data = JobData(job.id, "stats", "stats.csv").save()
        job_data.upload(output_path)

        logging.info("Finished generating .CSV file")

        job.update(progress=100, statusComment="Terminated")

    finally:
        logging.info("Deleting folder %s", working_path)
        shutil.rmtree(working_path, ignore_errors=True)

        logging.debug("Leaving run()")


if __name__ == '__main__':

    logging.debug("Command: %s", sys.argv)

    with cytomine.CytomineJob.from_cli(sys.argv) as cyto_job:
        run(cyto_job, cyto_job.parameters)
        