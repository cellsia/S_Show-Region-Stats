# python modules
from shapely.geometry import MultiPoint, Polygon
from datetime import datetime
import logging
import shutil
import pickle
import time
import json
import sys
import os

# cytomine modules
import cytomine
from cytomine.models.software import JobCollection, Job, JobDataCollection, JobData
from cytomine.models.annotation import AnnotationCollection, Annotation
from cytomine.models.property import Property, PropertyCollection
from cytomine.models.image import ImageInstance
from cytomine.models.project import Project
from cytomine.models.ontology import TermCollection, Term
from cytomine.models.user import UserJobCollection, UserJob
from cytomine.cytomine import Cytomine
from six import with_metaclass


# version control
__version__ = "1.6.1"


# constants
UPLOAD_JOB_NAME = "AI results upload"
UPLOAD_JOB_IMAGE_PARAMETER_NAME = "cytomine_image"
UPLOAD_JOB_FILENAME = "detections"
UPLOAD_JOB_FILEFORMAT = "json"
POSITIVE_KEY = "1.0"
NEGATIVE_KEY = "0.0"
POSITIVE_COLOR = "#68BC00"
NEGATIVE_COLOR = "#F44E3B"
HIDDEN_PROPERTY_PREFIX = "@"
HIDDEN_TERM_PREFIX = "@"
STATS_FILE_NAME = "stats.json"
STATS_FILE_TYPE =  "stats"

# ------------------------------- Support functions -------------------------------
get_new_delta = lambda n, a, b: (b - a) / n

def process_points(points):
    pts = [[p["x"],p["y"]] for p in points]
    return pts

def process_polygon(polygon):
    pol = str(polygon)[7:].rstrip("(").lstrip(")").split(",")
    for i in range(0, len(pol)):
        pol[i] = pol[i].rstrip(" ").lstrip(" ")
        pol[i] = pol[i].rstrip(")").lstrip("(").split(" ")
        pol[i][0] = float(pol[i][0])
        pol[i][1] = float(pol[i][1])
        pol[i] = tuple(pol[i])
    return pol

def update_properties(instance, properties):
    current_properties = PropertyCollection(instance).fetch()
    for k, v in properties.items():
        current_property = next((p for p in current_properties if p.key == HIDDEN_PROPERTY_PREFIX+k), None)
        if current_property:
            current_property.fetch()
            current_property.value = v
            current_property.update()
        else:
            Property(instance, key=HIDDEN_PROPERTY_PREFIX+k, value=v).save()


def _load_multi_class_points(image_id: str, multipoint: MultiPoint, key: str, annotation_id: int, parameters, hour) -> None:

    project = Project().fetch(parameters.cytomine_id_project)
    termscol = TermCollection().fetch_with_filter("ontology", project.ontology)    

    if key == POSITIVE_KEY:
        t = next(iter([t.id for t in termscol if "pos" in t.name]))
    else:
        t = next(iter([t.id for t in termscol if "neg" in t.name]))
    
    
    
    annotations = AnnotationCollection()
    annotations.append(Annotation(location=multipoint.wkt, id_image=image_id, id_project=parameters.cytomine_id_project, id_terms=[t]))
    annotations.save()      

    return None
    

# ------------------------------- Step functions -------------------------------

# STEP 0: delete old results
def delete_results(parameters):

    userjobs = UserJobCollection().fetch_with_filter("project", parameters.cytomine_id_project)
    ids = [userjob.id for userjob in userjobs]
    delta = 90

    annotations = AnnotationCollection()
    annotations.project = parameters.cytomine_id_project
    annotations.users = ids
    annotations.showTerm = True
    annotations.fetch()    

    if parameters.images_to_analyze:
        for annotation in annotations:   
            if annotation.image == parameters.images_to_analyze:     
                userjob = UserJob().fetch(id=annotation.user)
                with Cytomine(host=parameters.cytomine_host, public_key=userjob.publicKey, private_key=userjob.privateKey) as cytomine:
                    annotation.delete()
    
    else:
        for annotation in annotations:        
            userjob = UserJob().fetch(id=annotation.user)
            with Cytomine(host=parameters.cytomine_host, public_key=userjob.publicKey, private_key=userjob.privateKey) as cytomine:
                annotation.delete()

    return None

# STEP 1: get uploaded results
def get_uploaded_results(parameters, job):

    # progress bar status
    delta = 0

    # store the results {image: results}
    results = {}
    
    jobs = JobCollection()
    jobs.project = parameters.cytomine_id_project
    jobs.fetch()

    # get just the upload names
    upload_jobs_ids = [j.id for j in jobs if j.name[:len(UPLOAD_JOB_NAME)] == UPLOAD_JOB_NAME]
   
    # filter by image
    for job_id in upload_jobs_ids:
    
            jobparams = Job().fetch(job_id).jobParameters
            upload_image = [p["value"] for p in jobparams if (p["name"] == UPLOAD_JOB_IMAGE_PARAMETER_NAME)][0]
            
            if int(upload_image) == parameters.images_to_analyze:
                results[int(upload_image)] = job_id

            if not(parameters.images_to_analyze):
                results[int(upload_image)] = job_id
            

    for image_id, job_id in results.items():

        jobdatacol = JobDataCollection().fetch_with_filter(key="job", value=job_id)
        for data in jobdatacol:

            jobdata = JobData().fetch(data.id)
            filename = jobdata.filename

            if UPLOAD_JOB_FILENAME in filename:
                try:
                    jobdata.download(os.path.join("tmp/", filename))
                except AttributeError:
                    continue

            if filename[-4:] == UPLOAD_JOB_FILEFORMAT:

                with open("tmp/"+filename, 'r') as json_file:
                    data = json.load(json_file)
                    for key, value in data.items():
                        data[key] = MultiPoint(process_points(value))
                    json_file.close()

                results[image_id] = data

        # update progress
        delta += get_new_delta(len(results), 0, 10)
        job.update(progress=int(delta), statusComment="getting uploaded results")

    os.system("rm tmp/detections*")
    return results


# STEP 2: calculate image stats
def calculate_image_stats(results, job):

    # progress bar status
    delta = 10

    # store image stats
    image_stats = {}

    for image_id, data in results.items():

        for key, points in data.items():
            if key == POSITIVE_KEY:
                image_positives = len(points)
            elif key == NEGATIVE_KEY:
                image_negatives = len(points)

        total = image_negatives + image_positives
        if total != 0:
            ipositivity = round((image_positives * 100)/(image_positives + image_negatives), 2)
            inegativity = round((image_negatives * 100)/(image_positives + image_negatives), 2)
        else:
            ipositivity, inegativity = 0, 0


        image_stats[image_id] = {
            "general_info":{},
            "annotations_info":{}
        }

        image_stats[image_id]["general_info"] = {
            "image_count":image_positives + image_negatives,
            "image_positives":image_positives,
            "image_negatives":image_negatives,
            "image_positivity":ipositivity,
            "image_negativity":inegativity, 
            "image_annotated_area":0,
            "total_annotations_count":0,
            "total_annotations_positives":0,
            "total_annotations_negatives":0,
            "total_annotations_positivity":0,
            "total_annotations_negativity":0
        }

        # ----- upload image properties -----
        image = ImageInstance().fetch(id=image_id)
        update_properties(image, image_stats[image_id]["general_info"])

        # update progress
        delta += get_new_delta(len(results), 10, 20)
        job.update(progress=int(delta), statusComment="getting uploaded results")

    return image_stats


# STEP 3: get manual annotations
def get_manual_annotations(params):

    annotations = AnnotationCollection()
    annotations.project = params.cytomine_id_project

    if params.images_to_analyze:
        annotations.image = params.images_to_analyze

    annotations.showWKT = True
    annotations.showMeta = True
    annotations.showGIS = True
    annotations.showTerm = True
    annotations.fetch()

    filtered_annotations = [anot for anot in annotations if (anot.term == [])] # take just the no term annotations

    return filtered_annotations

        
# STEP 4: process manual annotations  
def process_manual_annotations(manual_annotations, results, image_stats, parameters, job):

    # progress bar status
    delta = 30

    for annotation in manual_annotations:
        
        try:

            # ----- get anot stats -----
            polygon = Polygon(process_polygon(annotation.location)) # annotation geometry

            data = results[annotation.image]

            # store inside points
            ins_points = {
                POSITIVE_KEY:None,
                NEGATIVE_KEY:None
            }
            
            for key, points in data.items():
                inside_points = [p for p in points if polygon.contains(p)] # inside points

                if key == POSITIVE_KEY:
                    anot_pos = len(inside_points)
                elif key == NEGATIVE_KEY:
                    anot_neg = len(inside_points)

                try:

                    # ----- upload inside_points layers ------
                    inside_multipoint = MultiPoint(inside_points)
                    time = datetime.now()
                    hour = time.strftime('%H:%M:%S')
                    _load_multi_class_points(annotation.image, inside_multipoint, key, annotation.id, parameters, hour)
                
                    ins_points[key] = inside_multipoint
                    
                except:
                    pass

            # ----- upload inside points files -----
            filename = "tmp/inside_points_{}".format(annotation.id)
            with open(filename, "wb") as multipoint_file:
                pickle.dump(ins_points, multipoint_file, pickle.HIGHEST_PROTOCOL)
                multipoint_file.close()

            job_data = JobData(job.id, "inside_points", filename.split("/")[-1]).save()
            job_data.upload(filename)
            os.system("rm "+filename)

            # ----- get stats -----
            total = anot_pos + anot_neg 
            if total != 0:
                apositivity = round((anot_pos * 100)/(anot_pos + anot_neg), 2)
                anegativity = round((anot_neg * 100)/(anot_pos + anot_neg), 2)
            else:
                apositivity, anegativity = 0, 0

            image_stats[annotation.image]["annotations_info"][annotation.id] = {
                "annotation_count":anot_pos + anot_neg,
                "annotation_positives":anot_pos,
                "annotation_negatives":anot_neg,
                "annotation_positivity":apositivity,
                "annotation_negativity":anegativity,
                "annotation_area":round(annotation.area, 2)
            }
            

            image_stats[annotation.image]["general_info"]["image_annotated_area"] += round(annotation.area, 2)
            image_stats[annotation.image]["general_info"]["total_annotations_count"] += (anot_pos + anot_neg)
            image_stats[annotation.image]["general_info"]["total_annotations_positives"] += anot_pos
            image_stats[annotation.image]["general_info"]["total_annotations_negatives"] += anot_neg
            
            if image_stats[annotation.image]["general_info"]["total_annotations_count"] != 0:
                actual_stats = image_stats[annotation.image]["general_info"]
                image_stats[annotation.image]["general_info"]["total_annotations_positivity"] = round((actual_stats["total_annotations_positives"] * 100) / actual_stats["total_annotations_count"], 2)
                image_stats[annotation.image]["general_info"]["total_annotations_negativity"] = round((actual_stats["total_annotations_negatives"] * 100) / actual_stats["total_annotations_count"], 2)
            
            # ---- upload/update annotation properties -----
            update_properties(annotation, image_stats[annotation.image]["annotations_info"][annotation.id])          

            # update progress
            delta += get_new_delta(len(manual_annotations), 30, 90)
            job.update(progress=int(delta), statusComment="processing manual anotations")

        except:
            continue

    # ----- upload stats file -----
    f = open("tmp/"+STATS_FILE_NAME, "w+")
    json.dump(image_stats, f)
    f.close()

    job_data = JobData(job.id, STATS_FILE_TYPE, STATS_FILE_NAME).save()
    job_data.upload("tmp/"+STATS_FILE_NAME)
    os.system("rm tmp/"+STATS_FILE_NAME)

    return None


# ------------------------------- Main function -------------------------------
def run(job, parameters):

    # show version control and parameters
    logging.info("----- test software v%s -----", __version__)
    logging.info("Entering run(cyto_job=%s, parameters=%s)", job, parameters)

    # create working directory
    working_path = os.path.join("tmp", str(job.id))
    if not os.path.exists(working_path):
        logging.info("Creating working directory: %s", working_path)
        os.makedirs(working_path)


    try:

        # STEP 0: delete old results
        delete_results(parameters)

        # STEP 1: get uploaded results
        job.update(progress=0, statusComment="getting uploaded results")
        results = get_uploaded_results(parameters, job)
        
        if results == {}:
            job.update(progress=100, status=job.FAILED, statusComment="no results uploaded!") 
            sys.exit()

        # STEP 2: calculate image stats
        job.update(progress=10, statusComment="calculating image stats")
        image_stats = calculate_image_stats(results, job)

        # STEP 3: get manual annotations
        job.update(progress=20, statusComment="Getting manual annotations")
        manual_annotations = get_manual_annotations(parameters)

        if manual_annotations == []:

            # ----- upload stats file -----
            f = open("tmp/"+STATS_FILE_NAME, "w+")
            json.dump(image_stats, f)
            f.close()

            job_data = JobData(job.id, STATS_FILE_TYPE, STATS_FILE_NAME).save()
            job_data.upload("tmp/"+STATS_FILE_NAME)
            os.system("rm tmp/"+STATS_FILE_NAME)

            job.update(progress=90, statusComment="no manual annotations!") 

        else:    

            # STEP 4: process manual annotations  
            job.update(progress=30, statusComment="processing manual anotations")
            process_manual_annotations(manual_annotations, results, image_stats, parameters, job)

        job.update(progress=100, statusComment="job done!")

    finally:

        # delete tmp/ files
        logging.info("Deleting folder %s", working_path)
        shutil.rmtree(working_path, ignore_errors=True)
        logging.debug("Leaving the script...")

    return None



if __name__ == '__main__':

    logging.debug("Command: %s", sys.argv)

    with cytomine.CytomineJob.from_cli(sys.argv) as cyto_job:

        # log time
        start_time = time.time()
        run(cyto_job.job, cyto_job.parameters)
        logging.info("--- %s seconds ---" % (time.time() - start_time))
