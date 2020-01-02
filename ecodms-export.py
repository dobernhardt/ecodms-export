import click
import logging
import traceback
import sys
import requests
from requests.auth import HTTPBasicAuth
import json
import unicodedata
import re
import os.path
import glob
import shutil

_logger = None


def parse_folders (response_body):
    logger = _logger.getChild(parse_folders.__name__)
    json_response = json.loads(response_body)
    folders = {}
    for element in json_response:
        folders[element['oId']] = element['foldername']
    folders["0"] =  "not_assigned"
    return folders


def parse_doc_types (response_body):
    logger = _logger.getChild(parse_doc_types.__name__)
    json_response = json.loads(response_body)
    doc_types = {}
    for element in json_response:
        doc_types[str(element['id'])] = element['name']
    doc_types["0"] =  "not_assigned"
    return doc_types


def slugify(value, allow_unicode=False):
    """
    Convert to ASCII if 'allow_unicode' is False. Convert spaces to hyphens.
    Remove characters that aren't alphanumerics, underscores, or hyphens.
    Convert to lowercase. Also strip leading and trailing whitespace.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '.', value.lower()).strip()
    return re.sub(r'[-\s]+', '-', value)


@click.command()
@click.option('--debug/--no-debug', default=False)
@click.option('--export-json/--no-export-json',default=False,help="Dump the document classification meta data as json file next to the PDF")
@click.option('--host',default="ecodms",show_default=True,help="hostname of the ecodms system")
@click.option('--port',default="8180",show_default=True,help="port# of the ecodms api")
@click.option('--user',show_default=True,help="Username to access the ecodms system",required=True)
@click.option('--password',help="password to access the ecodms system",required=True)
@click.option('--archive-id',default=1,show_default=True,help="Archive ID to be used. In a default ecodms instance there is only one archive")
@click.option('--cache-dir',help="optional directory caching directory to limit repeated downloads from ecodms")
@click.option('--name-template',default="{year}/{folder}/{docart}/{cdate}_{docid}_{bemerkung}",show_default=True,help="Template for the exported filenames.")
@click.argument('export_dir')
def cli(debug,host,port,user,password,cache_dir,export_dir,archive_id,name_template,export_json):
    """This script exports the documents stored in the ecodms document management system into the the EXPORT_DIR directory.
    It uses the meta information to create the folder hierarchy and filenames. Optionally all meta information can be dumped as json next to the documents.
    """
    global _logger
    _logger = logging.getLogger ("ecodms")
    logger = _logger.getChild("cli")
    if debug:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s;[%(levelname)s] %(name)s - %(message)s')
    else:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s;[%(levelname)s] %(name)s - %(message)s')    
    logger.debug("Logging initiated")
    export_dir = os.path.abspath(export_dir)
    api_endpoint = "http://{}:{}/api".format(host,port)
    session = requests.Session()
    try:
        url = api_endpoint + "/test"
        logger.debug("GET {}".format(url))
        response = session.get(url)
    except Exception as e:
        logger.error("Failed to connect to ecodms API endpoint {}".format(api_endpoint)) 
        logger.error ("Exception: {}".format(e))
        return 1
    if not response.status_code == 200:
        logger.error ("Retrieved status code {} on test endpoint {}".format(response.status_code,api_endpoint))
        return 1
    # connect to ecodms
    url = "{}/connect/{}".format(api_endpoint,archive_id)
    logger.debug("GET {}".format(url))
    response = session.get(url,auth=HTTPBasicAuth(user, password))
    if not response.status_code == 200:
        logger.error ("Failed to authenticate. Got status code {}".format(response.status_code))
        return 1
    # read available folders
    url = "{}/folders".format(api_endpoint)
    logger.debug("GET {}".format(url))
    response = session.get(url)
    if not response.status_code == 200:
        logger.error ("Failed to authenticate. Got status code {}".format(response.status_code))
        return 1
    folders = parse_folders(response.content)
    # read document type mapping
    url = "{}/types".format(api_endpoint)
    logger.debug("GET {}".format(url))
    response = session.get(url)
    if not response.status_code == 200:
        logger.error ("Failed to authenticate. Got status code {}".format(response.status_code))
        return 1
    doc_types = parse_doc_types(response.content)
    min_doc_id = 0 
    doc_id_incr = 50
    while(True):
        logger.info ("Processing doc# {} to {}".format(min_doc_id,min_doc_id+doc_id_incr))
        filter = """[{{"classifyAttribut":"docid", "searchOperator":">=", "searchValue":"{}"}},{{"classifyAttribut":"docid", "searchOperator":"<", "searchValue":"{}"}}]""".format(min_doc_id,min_doc_id+doc_id_incr)
        logger.debug ("Filter: {}".format(filter))
        url = "{}/searchDocuments".format(api_endpoint)
        response = session.post(url,json=json.loads(filter))
        if not response.status_code == 200:
            logger.error ("Failed to retrieve document list. Got status code {}".format(response.status_code))
            return 1
        json_response = json.loads(response.content)
        if len(json_response)==0: # if no more documents have been found
            break
        for doc in json_response:
            try:
                doc_attr = doc['classifyAttributes']
                doc_attr['folder'] = folders[doc_attr['folder']]
                doc_attr['docart'] = doc_types[doc_attr['docart']]
                doc_attr['year'] = doc_attr['cdate'][0:4]
                doc_attr['month'] = doc_attr['cdate'][5:7]
                doc_attr['day'] = doc_attr['cdate'][8:10]
                for attr_key in doc_attr.keys():
                    doc_attr[attr_key] = slugify(doc_attr[attr_key])
                target_filename_base = os.path.join(export_dir,name_template.format(**doc_attr))
                target_filename_pdf = target_filename_base + ".pdf"
                target_filename_json = target_filename_base + ".json"
                logger.debug ("Processing doc# {} => {}".format(doc['docId'],target_filename_pdf))
                if os.path.exists(target_filename_pdf):
                    logger.debug ("File already exists")
                else:
                    target_dir = os.path.dirname(target_filename_pdf)
                    if not os.path.isdir (target_dir):
                        logger.info ("Creating directory {}".format(target_dir))
                        os.makedirs(target_dir)
                    found_in_cache = False
                    # if an cache directory was defined we first look there
                    if not cache_dir is None:
                        filename_match = glob.glob("{}/{}_*".format(cache_dir,doc['docId']))
                        if len(filename_match)>0:
                            logger.debug("{} => {}".format(filename_match[0],target_filename_pdf))
                            shutil.copy2(filename_match[0],target_filename_pdf)
                            found_in_cache = True
                        else:
                            logger.debug("Did not find a matching filename for doc #{} in cache".format(doc['docId']))
                    if not found_in_cache: 
                        url = "{}/document/{}".format(api_endpoint,doc['docId'])
                        logger.debug("GET {}".format(url))
                        response = session.get (url)
                        if not response.status_code == 200:
                            logger.error ("Failed to retrieve document file for doc#{}. Got status code {}".format(doc['docId'],response.status_code))
                        else:
                            open(target_filename_pdf, 'wb').write(response.content)
                            if not cache_dir is None:
                                # use a naming pattern for cache file that is compatible to the manual ecodms export to be able to prepopulate the cache with a manual export
                                shutil.copy2(target_filename_pdf,os.path.join(cache_dir,"{}_.pdf".format(doc['docId'])))
                if export_json and not os.path.exists(target_filename_json):
                    with open(target_filename_json, 'w') as outfile:
                        json.dump(doc, outfile, indent=4)

            except:
                logger.error ("Caught exception while processing document #{}".format(doc['docId']))
                raise
        min_doc_id = min_doc_id + doc_id_incr
    url = "{}/disconnect".format(api_endpoint)
    logger.debug("GET {}".format(url))
    response = session.get(url)
    


if __name__ == '__main__':
    try:
        if (sys.version_info[0]<3) or (sys.version_info[1]<5):
            _logger.error ("At least python 3.5 is required")
        else:
            cli()
    except SystemExit as ex:
        sys.exit(ex.code)
    except:
        if _logger is None:
            logging.getLogger().error ("Unexpected exception caught:\n{}".format(traceback.format_exc()))
        else:
            _logger.error ("Unexpected exception caught:\n{}".format(traceback.format_exc()))
        sys.exit(1)
