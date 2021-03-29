import logging
import sys
import json
import os
from argparse import ArgumentParser

from cytomine import Cytomine
from cytomine.models import AnnotationCollection, JobCollection, JobData, Project, Term, UserJobCollection, Annotation
from cytomine.models.software import JobDataCollection, JobParameterCollection
from cytomine.models.ontology import TermCollection


def get_stats_annotations(params):

     with Cytomine(host=params.cytomine_host, public_key=params.cytomine_public_key, private_key=params.cytomine_private_key, verbose=logging.INFO) as cytomine:
        cytomine.open_admin_session()

        users = UserJobCollection().fetch_with_filter("project", params.cytomine_id_project)
        ids = [user.id for user in users]
        print(ids)

        annotations = AnnotationCollection()

        annotations.project = params.cytomine_id_project
        annotations.users = ids

        annotations.fetch()

        ids_to_delete = [annotation.id for annotation in annotations]
        [Annotation().delete(id=id_) for id_ in ids_to_delete]

        return None

def get_results(params):
    
    with Cytomine(host=params.cytomine_host, public_key=params.cytomine_public_key, private_key=params.cytomine_private_key, verbose=logging.INFO) as cytomine:

        results = [] # array con resultados 
        equiv = {} # diccionario de equivalencias (filename - cytomine_image_term_id)

        # sacamos lista con todos los job id's
        jobs = JobCollection()
        jobs.project = params.cytomine_id_project
        jobs.fetch()

        
        jobs_ids = [job.id for job in jobs if (job.name[:17] != "Show Region Stats")]
        print(jobs_ids)


        """for job_id in jobs_ids:

            # para cada job sacamos prametros y coleccion de datos
            jobparamscol = JobParameterCollection().fetch_with_filter(key="job", value=job_id)
            jobdatacol = JobDataCollection().fetch_with_filter(key="job", value=job_id)

            for job in jobdatacol:

                jobdata = JobData().fetch(job.id)
                filename = jobdata.filename

                allowed_params = ["cytomine_image", "cytomine_id_image", "cytomine_image_instance"]
                [equiv.update({filename:int(param.value)}) for param in jobparamscol if (str(param).split(" : ")[1] in allowed_params) ]

                # si el .json tiene "detections en el nombre de archivo lo descargamos y lo metemos en la carpeta tmp/"
                if "detections" in filename:
                    try:
                        jobdata.download(os.path.join("tmp/", filename))
                    except AttributeError:
                        continue

        # cargamos los resultados a partir de los archivos que hemos descargado
        temp_files = os.listdir("tmp")
        for i in range(0, len(temp_files)):
            if temp_files[i][-4:] == "json":
                filename = temp_files[i]
                try:
                    image = equiv[filename] # recuperamos la imagen a la que hace refereancia cada archivo bassandonos en el dic de equivalencias
                    with open("tmp/"+filename, 'r') as json_file:
                        data = json.load(json_file)
                        json_file.close()
                    
                    results.append({"image":image,"data":data}) # añadimos el resultado con su imagen asociada
                except KeyError:
                    continue

        os.system("cd tmp&&rm detections*") # eliminamos archivos temporales"""

        return results

def create_term(params):

    with Cytomine(host=params.cytomine_host, public_key=params.cytomine_public_key, private_key=params.cytomine_private_key, verbose=logging.INFO) as cytomine:

        project = Project().fetch(params.cytomine_id_project)

        termscol = TermCollection().fetch_with_filter("project", project.id)
        [print(term) for term in termscol]
        

        term = Term("Hello Term", project.ontology, "F44E3B").save()

        termscol = TermCollection().fetch_with_filter("project", project.id)
        [print(term) for term in termscol]

    return None

def delete_term(params):

    with Cytomine(host=params.cytomine_host, public_key=params.cytomine_public_key, private_key=params.cytomine_private_key, verbose=logging.INFO) as cytomine:
        
        project = Project().fetch(params.cytomine_id_project)

        termscol = TermCollection().fetch_with_filter("project", project.id)
        [print(term) for term in termscol]


        
        t_names = [t.id for t in termscol if t.name == "Hello Term"]
        Term().delete(id=t_names[0])

    
        termscol = TermCollection().fetch_with_filter("project", project.id)
        [print(term) for term in termscol]

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


    get_stats_annotations(params)

    #results = get_results(params)

    #create_term(params)

#    delete_term(params)

    
    
    