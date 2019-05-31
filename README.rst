DefectDojo API
==============

This is changed version of `aaronweaver/defectdojo_api <https://github.com/aaronweaver/defectdojo_api>`

Tested python version: python 3.6 - 3.7

A Python API wrapper for `DefectDojo <https://github.com/OWASP/django-DefectDojo>`_, an AppSec and Security Vulnerability Management tool.

This package implements API functionality available within Dojo.

Usage
-----------
First of all, configuration file (config.example.yaml) should be changed
according to your DefectDojo installation.

CLI Usage
-----------
Available options:
```
$ python start.py --help
Usage: start.py [OPTIONS] COMMAND [ARGS]...


  CLI for Defect Dojo.

Options:
  -c, --config TEXT  Configuration file path. Default is 'config.yaml'
  --help             Show this message and exit.

Commands:
  engagement-delete     Delete engagement.
  test-delete-all       Delete all tests.
  test-delete-findings  Delete findings in test.
  update                Products update.
```

Available `update` options:
```
$ python start.py update --help

Usage: start.py update [OPTIONS]

  Products update. By default all product will be updated

Options:
  -t, --type [all|engagement|nikto]
                                  Update type:
                                  all (default) - updatel all
                                  products from Appscreener + Nessus scanners
                                  engagement - update specific engagement from
                                  Appscreener + Nessus scanners
                                  nikto - update
                                  from nikto scanner
  -e, --eng_id INTEGER            Engagement ID
  -f, --file_path TEXT            Path to nikto scan results
  -d, --domain TEXT               Scanned domain name
  --help                          Show this message and exit.
```

Usage As A Package
-----------
```
from defectdojo_api import uploader
upload = uploader.Uploader(config=config_path)
upload.update_all()
```
