New repositories must be structured as follows.

There are three top level directories: 
    A. "src" - contains all code necessary for the evaluation to run 
    B. "docs" - contains .md files containing information about the codebase 
    C. "logs" - contains all results from evaluation runs 
    D. "experiments" - contains scripts used to run evaluation. This will always contain at least two files: 
        1. setup_experiment.sh: Has logic for setting up all reproducibility & logging for the experiment 
        2. test_config.sh: Is a config file that is a template for all experiments run. It has just one argument -
    the id of the experiment being run. If the id is is "test", then this does not do any reproducibiltiy or logging \

To run an experiment, the user must copy test_config.sh, rename it, and modify it so that the right values of parameters to the experiment are passed. The copied version should live in the project's main directory.
