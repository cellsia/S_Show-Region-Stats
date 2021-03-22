import logging
import sys

import cytomine

__version__ = "1.0.9"


def run(cyto_job, parameters):

    logging.info("----- test software v%s -----", __version__)
    logging.info("Entering run(cyto_job=%s, parameters=%s)", cyto_job, parameters)

if __name__ == '__main__':

    logging.debug("Command: %s", sys.argv)

    with cytomine.CytomineJob.from_cli(sys.argv) as cyto_job:

        run(cyto_job, cyto_job.parameters)