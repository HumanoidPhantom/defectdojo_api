"""
Example written by Aaron Weaver <aaron.weaver@owasp.org>
as part of the OWASP DefectDojo and OWASP AppSec Pipeline Security projects

Description: Creates a product in DefectDojo and returns information about the newly created product
"""
from defectdojo_api import defectdojo

import os

# Setup DefectDojo connection information
host = 'http://localhost:8000'
api_key = os.environ['DOJO_API_KEY']
user = 'admin1'

#Optionally, specify a proxy
proxies = {
  'http': 'http://localhost:8080',
  'https': 'http://localhost:8080',
}
#proxies=proxies


# Instantiate the DefectDojo api wrapper
dd = defectdojo.DefectDojoAPI(host, api_key, user, proxies=proxies, debug=False)

# List Tool Types
tool_types = dd.list_tool_types()

#print "Configured Tool Types"
#print tool_types.data_json(pretty=True)

list_credential_mappings = dd.list_credential_mappings(product_id_in=2)
print "Creds"
#print list_credential_mappings.data_json(pretty=True)

for cred in list_credential_mappings.data["objects"]:
    print cred["id"]
    print cred["credential"]
    get_credential = dd.get_credential(dd.get_id_from_url(cred["credential"]))
    print get_credential.data["selenium_script"]
    if get_credential.data["selenium_script"] != "None":
        file = open("testfile.py","w")
        file.write(get_credential.data["selenium_script"])
        file.close()
    print get_credential.data_json(pretty=True)


"""
list_containers = dd.list_containers()
print "Containers"
print list_containers.data_json(pretty=True)
# Search Tool Types by Name
tool_types = dd.list_tool_types(name="Source Code Repository")

print "Source Code Repository Tool Types"
print tool_types.data["objects"][0]['id']
print tool_types.data_json(pretty=True)

print "Configured Source Code Repository Tools"
tool = dd.list_tools(tool_type_id=tool_types.data["objects"][0]['id'])
print tool.data_json(pretty=True)

print "Products Configured to use source code repos"
tool = dd.list_tool_products(tool_configuration_id=tool.data["objects"][0]['id'])
print tool.data_json(pretty=True)
"""
