# python modules
from shapely.geometry import Polygon, MultiPoint
from datetime import datetime
import logging
import shutil
import json
import sys
import os

# cytomine modules 
import cytomine
from cytomine.models.annotation import Annotation, AnnotationCollection
from cytomine.models.software import Job, JobCollection, JobData, JobDataCollection, JobParameterCollection
from cytomine.models.image import ImageInstance
from cytomine.models.property import Property, PropertyCollection
from cytomine.cytomine import Cytomine
from cytomine.models import annotation
from cytomine.models.ontology import Term, TermCollection
from cytomine.models.project import Project
from cytomine.models.user import UserJobCollection


# script version 
__version__ = "1.3.8" 



# --------------------------------------------------------- Support Functions ---------------------------------------------------------
get_new_delta = lambda n, a, b: (b - a) / n

def process_polygon(polygon):
    pol = str(polygon)[7:].rstrip("(").lstrip(")").split(",")
    for i in range(0, len(pol)):
        pol[i] = pol[i].rstrip(" ").lstrip(" ")
        pol[i] = pol[i].rstrip(")").lstrip("(").split(" ")
        pol[i][0] = float(pol[i][0])
        pol[i][1] = float(pol[i][1])
        pol[i] = tuple(pol[i])
    return pol

def process_points(points):
    pts = [[p["x"],p["y"]] for p in points]
    return pts

def _generate_multipoints(detections: list) -> MultiPoint:
    points = []
    for detection in detections:
        points.append((detection['x'], detection['y']))

    return MultiPoint(points=points)

def _load_multi_class_points(job: Job, image_id: str, detections: dict, id_: int, params, hour, mantener_ids) -> None:

    terms = [key for key,value in detections.items()]

    project = Project().fetch(params.cytomine_id_project)
    termscol = TermCollection().fetch_with_filter("ontology", project.ontology)
    

    for idx, points in enumerate(detections.values()):

        if terms[idx] == "1.0":
            term_name = "POS_{}_{}".format(id_, hour)
            term1 = Term(term_name, project.ontology, "#68BC00").save()
            
        else:
            term_name = "NEG_{}_{}".format(id_, hour)
            term1 = Term(term_name, project.ontology, "#F44E3B").save()
            

        multipoint = _generate_multipoints(points)
        
        termscol = TermCollection().fetch_with_filter("ontology", project.ontology)
            
        t1 = [t.id for t in termscol if t.name == term_name]
        mantener_ids.append(t1[0])
        
        annotations = AnnotationCollection()
        annotations.append(Annotation(location=multipoint.wkt, id_image=image_id, id_project=params.cytomine_id_project, id_terms=t1))
        annotations.save()        

    return None



# --------------------------------------------------------- Steps Functions ---------------------------------------------------------

# STEP 1: get manual annotations
def get_manual_annotations(params):

    annotations = AnnotationCollection()
    annotations.project = params.cytomine_id_project

    if type(params.images_to_analyze) != "NoneType":
        annotations.image = params.images_to_analyze

    annotations.showWKT = True
    annotations.showMeta = True
    annotations.showGIS = True
    annotations.showTerm = True
    annotations.fetch()

    return annotations

# STEP 2: get uploaded results
def get_uploaded_results(params, job):

    file_term_equivalences = {}
    delta = 5

    jobs = JobCollection()
    jobs.project = params.cytomine_id_project
    jobs.fetch()
    jobs_ids = [j.id for j in jobs if (j.name[:17] != "Show Region Stats")]

    for job_id in jobs_ids:

        jobparamscol = JobParameterCollection().fetch_with_filter(key="job", value=job_id)
        jobdatacol = JobDataCollection().fetch_with_filter(key="job", value=job_id)

        for _job in jobdatacol:

            jobdata = JobData().fetch(_job.id)
            filename = jobdata.filename

            allowed_params = ["cytomine_image", "cytomine_id_image", "cytomine_image_instance"]
            [file_term_equivalences.update({filename:int(param.value)}) for param in jobparamscol if (str(param).split(" : ")[1] in allowed_params) ]

            if "detections" in filename:
                try:
                    jobdata.download(os.path.join("tmp/", filename))
                except AttributeError:
                    continue

        delta += get_new_delta(len(jobs_ids), 5, 20)
        job.update(progress=int(delta), statusComment="getting uploaded results")

    results = []
    temp_files =  os.listdir("tmp")
    for i in range(0, len(temp_files)):
        if temp_files[i][-4:] == "json":
            filename = temp_files[i]
            try:
                image = file_term_equivalences[filename]
                with open("tmp/"+filename, 'r') as json_file:
                    data = json.load(json_file)
                    json_file.close()
                results.append({"image":image, "data":data})
            except KeyError:
                continue

    os.system("cd tmp && rm detections")
    return results
            
# STEP 3: calculate stats and get inside points
def get_stats_and_inside_points(annotations, results, job):

    stats = {}
    inside_points_list = []
    delta = 20 

    for annotation in annotations:
       
        inside_points = {}
        polygon = Polygon(process_polygon(annotation.location))
        
        for result in results: 
            if result["image"] == annotation.image:

                all_points = result["data"]
                
                for key, value in all_points.items():

                    pts = MultiPoint(process_points(value))
                    ins_pts = [p for p in pts if polygon.contains(p)]

                    ins_p = [{"x":p.x, "y":p.y} for p in ins_pts]
                    inside_points.update({key:ins_p})

                    if key == "1.0":
                        anot_pos = len(ins_pts)
                    elif key == "2.0":
                        anot_neg = len(ins_pts)

                if not annotation.image in stats.keys():
                    stats[annotation.image] = {
                        "general_info":{},
                        "annotations_info":{}
                    }

                stats[annotation.image]["annotations_info"][annotation.id] = {
                    "annotation_count":anot_pos + anot_neg,
                    "annotation_positives":anot_pos,
                    "annotation_negatives":anot_neg,
                    "annotation_area":annotation.area
                }

        inside_points_list.append([annotation.id, inside_points])
        delta += get_new_delta(len(annotations), 20, 60)
        job.update(progress=int(delta), statusComment="calculating stats and getting inside points")

    for image_id, image_info in stats.items():
        image_count, image_positives, image_negatives, image_annotated_area = 0, 0, 0, 0
        for annotation_id, annotation_info in stats[image_id]["annotations_info"].items():
            anot_info =  stats[image_id]["annotations_info"][annotation_id]
            image_count += anot_info["annotation_count"]
            image_positives += anot_info["annotation_positives"]
            image_negatives += anot_info["annotation_negatives"]
            image_annotated_area += anot_info["annotation_area"]

        stats[image_id]["general_info"] = {
            "image_count" : image_count,
            "image_positives": image_positives,
            "image_negatives": image_negatives,
            "image_annotated_area" : image_annotated_area
        }

    return stats, inside_points_list
   
# STEP 6: update image & annotations properties
def update_properties(stats, job): 

    delta = 75

    for image_id, image_info in stats.items():

        image = ImageInstance().fetch(id=int(image_id))

        for k, v in image_info["general_info"].items():
            current_properties = PropertyCollection(image).fetch()
            current_property = next((p for p in current_properties if p.key == k), None)
            if current_property:
                current_property.fetch()
                current_property.value = v 
                current_property.update()
            else:
                Property(image, key=k, value=v).save()

        for anot_id, anot_info in image_info["annotations_info"].items():
            annotation = Annotation().fetch(id=int(anot_id))
            for k, v in anot_info.items():
                current_properties = PropertyCollection(annotation).fetch()
                current_property = next((p for p in current_properties if p.key == k), None)
                
                if current_property:
                    current_property.fetch()
                    current_property.value = v 
                    current_property.update()
                else:
                    Property(annotation, key=k, value=v).save()

            delta += get_new_delta(len(image_info["annotations_info"].keys()), 75, 85)
        job.update(progress=int(delta), statusComment="updating image & annotations properties")

    return None
                
 # STEP 8: remove previous results
def delete_results(params, lista_id, job):

    users = UserJobCollection().fetch_with_filter("project", params.cytomine_id_project)
    ids = [user.id for user in users]
    delta = 95

    annotations = AnnotationCollection()
    annotations.project = params.cytomine_id_project
    annotations.users = ids
    annotations.showTerm = True
    annotations.fetch()
    
    
    cyto_job.open_admin_session()
    ids_to_delete = [annotation.id for annotation in annotations if not (annotation.term[0] in lista_id)]
    
    with Cytomine(host=params.cytomine_host, public_key=params.cytomine_public_key, private_key=params.cytomine_private_key, verbose=logging.INFO) as cytomine:
        cytomine.open_admin_session()
        [Annotation().delete(id=id_) for id_ in ids_to_delete]
        
        
        project = Project().fetch(params.cytomine_id_project)
        termscol = TermCollection().fetch_with_filter("project", project.id)
        ids_to_delete = [t.id for t in termscol if (t.name != "Stats" and not (t.id in lista_id))]

        for id_ in ids_to_delete:
            Term().delete(id=id_)
            delta += get_new_delta(len(ids_to_delete), 95, 100)
            job.update(progress=int(delta), statusComment="Removing previous results")

    return None



# --------------------------------------------------------- Main Function ---------------------------------------------------------
def run (cyto_job, parameters):

    # version control and input parameters
    logging.info("----- test software v%s -----", __version__)
    logging.info("Entering run(cyto_job=%s, parameters=%s)", cyto_job, parameters)

    # get the job (will be used later)
    job = cyto_job.job

    # create working folder 
    working_path = os.path.join("tmp", str(job.id))
    if not os.path.exists(working_path):
        logging.info("Creating working directory: %s", working_path)
        os.makedirs(working_path)

    try: 

        # STEP 1: get manual annotations
        job.update(progress=0, statusComment="Getting manual annotations")
        manual_annotations = get_manual_annotations(parameters)

        # STEP 2: get uploaded results
        job.update(progress=5, statusComment="getting uploaded results")
        results = get_uploaded_results(parameters, job)

        # STEP 3: calculate stats and get inside points
        job.update(progress=20, statusComment="calculating stats and getting inside points")
        stats, inside_points_list = get_stats_and_inside_points(manual_annotations, results, job)

        # STEP 4: upload files with the stats 
        job.update(progress=60, statusComment="uploading 'stats.json' file")

        output_path = os.path.join(working_path, "stats.json")
        f = open(output_path, "w+")
        json.dump(stats, f)
        f.close()

        job_data = JobData(job.id, "stats", "stats.json").save()
        job_data.upload(output_path)

        # STEP 5: upload files with the inside points
        job.update(progress=65, statusComment="uploading 'inside_points.json' files")
        delta = 65

        for item in inside_points_list:
            
            output_path2 = os.path.join(working_path, "inside_points_{}.json".format(item[0]))
            f = open(output_path2, "w+")
            json.dump(item[1], f)
            f.close()

            job_data = JobData(job.id, "detections", "inside_points_{}.json".format(item[0])).save()
            job_data.upload(output_path2)
            

            delta += get_new_delta(len(inside_points_list), 65, 75)
            job.update(progress=int(delta), statusComment="uploading 'inside_points.json' files")

        # STEP 6: update image & annotations properties
        job.update(progress=75, statusComment="updating image & annotations properties")
        update_properties(stats, job)

        # STEP 7: upload detections layers
        job.update(progress=75, statusComment="uploadind detections layers")
        delta = 85

        time = datetime.now()
        hour = time.strftime('%H:%M:%S')
        keep_anot_ids = []

        for item in inside_points_list:
            anot_id = int(item[0])
            annotation = Annotation().fetch(id=anot_id)
            image_id = annotation.image
            detections = item[1]

            boolean = True
            for key, value in detections.items():
                if len(value) == 0:
                    boolean = False
            
            if boolean:
                _load_multi_class_points(job, image_id, item[1], anot_id, parameters, hour, keep_anot_ids)
            else:
                continue
            
            delta += get_new_delta(len(inside_points_list), 85, 95)
            job.update(progress=int(delta), statusComment="uploadind detections layers")


        # STEP 8: remove previous results
        delete_results(parameters, keep_anot_ids, job)
        job.update(progress=100, statusComment="Job Done")

    finally:

        # delete tmp files before closing the connection
        logging.info("Deleting folder %s", working_path)
        shutil.rmtree(working_path, ignore_errors=True)
        logging.debug("Leaving run()")

    return None

if __name__ == '__main__':

    logging.debug("Command: %s", sys.argv)

    # connect to cytomine instance and create a new job 
    with cytomine.CytomineJob.from_cli(sys.argv) as cyto_job:

        run(cyto_job, cyto_job.parameters)