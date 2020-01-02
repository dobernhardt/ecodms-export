# Export for ecodms

## Overview

This script is intended to export the content of an ecodms (https://www.ecodms.de) document archive to the filesystem while preserving most of the metadata. The script creates a directory structure in the filesystem mimicking the virtual folders inside eocdms and using meta data for the filename. To extract the ecodms content the script uses the REST API provided by ecodms (https://www.ecodms.de/index.php/en/ecodms-api/ecodms-api-rest-service)

## Prerequisits

To use the script the API needs to be enabled and a license for API calls needs to be available. With a normal license only 10 API calls per month are possible. Although calls to querry for meta data are not counted the licenses are required for downloading PDFs.

## Using cache dir with manual export to bypass limited number of API calls

As the number of file downloads via the API is limited an alternative was implemented. Within the ecodms client there is an option to export files (Menu files/export). You could mark all documents and export those to a local directory. As these exported files are prefixed with the document number this epxort could be used as an alternative source for getting the PDFs by the script. If you want to use this feature use the --cache-dir option to specify the path to this directory. This is especially usefull to perform the initial export. As long as you are only adding a few files per month (i.e. less than 10) you could use the download functionality for all future increments. This cache-dir is also populated by ecodms-export.py with every download and will prevent subsequent downloads of identical PDFs (i.e. for subsequent runs or documents with multiple classifications)

## Export file names

With the --name-template option it can be specified how the exported filenames are derived from the document metadata. Any attribute available in the metadata json can be used as a token. Additionally the attributes year, month and day are derived from cdate to allow for a year prefix.
