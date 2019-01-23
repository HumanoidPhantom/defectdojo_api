from defectdojo_api import defectdojo, connector
import click

@click.group()
def main():
    """CLI for Defect Dojo"""
    pass

    # tool_types = dd_v1.list_tools()
    #
    # print(tool_types.data_json(pretty=True))
    # exit()
    # # instantiate the DefectDojo api wrapper
    # dd_v1 = defectdojo.DefectDojoAPI(host, api_key, user, debug=False, api_version='v1')
    # dd_v2 = defectdojo.DefectDojoAPI(host, api_key2, user, debug=False, api_version='v2')
    #
    # tool_types = dd_v1.list_tools()
    #
    # print(tool_types.data_json(pretty=True))
    # exit()
    # print(tool_types.data['results'])
    # for type in tool_types.data['results']:
    #     print(type['url'])
    #     type_info = dd.list_tool_types(type['url'])
    #     print(type_info.data_json(pretty=True))
    #
    #
    #
    #
    #
    # # TODO: Добавление новых проектов
    # # TODO: Указание в конфигурационном файле путей к сканерам / id-ков проектов
    #
    #
    #
    #
    #
    # # If you need to disable certificate verification, set verify_ssl to False.
    # # dd = defectdojo.DefectDojoAPI(host, api_key, user, verify_ssl=False
    #
    # # Create a product
    # # prod_type = 1 #1 - Research and Development, product type
    # # product = dd.create_product("API Product Test", "This is a detailed product description.", prod_type)
    # #
    # # if product.success:
    # # # Get the product id
    # # product_id = product.id()
    # # print "Product successfully created with an id: " + str(product_id)
    # #
    # # #List Products
    # # products = dd.list_products()
    # #
    # # if products.success:
    # #     print(products.data_json(pretty=True))  # Decoded JSON object
    # #
    # # for product in products.data["objects"]:
    # #     print(product['name'])  # Print the name of each product
    # # else:
    # #     print(products.message)
    # print(tool_types.data['results'])
    # for type in tool_types.data['results']:
    #     print(type['url'])
    #     type_info = dd.list_tool_types(type['url'])
    #     print(type_info.data_json(pretty=True))





    # TODO: Добавление новых проектов
    # TODO: Указание в конфигурационном файле путей к сканерам / id-ков проектов





    # If you need to disable certificate verification, set verify_ssl to False.
    # dd = defectdojo.DefectDojoAPI(host, api_key, user, verify_ssl=False

    # Create a product
    # prod_type = 1 #1 - Research and Development, product type
    # product = dd.create_product("API Product Test", "This is a detailed product description.", prod_type)
    #
    # if product.success:
    # # Get the product id
    # product_id = product.id()
    # print "Product successfully created with an id: " + str(product_id)
    #
    # #List Products
    # products = dd.list_products()
    #
    # if products.success:
    #     print(products.data_json(pretty=True))  # Decoded JSON object
    #
    # for product in products.data["objects"]:
    #     print(product['name'])  # Print the name of each product
    # else:
    #     print(products.message)

@main.command()
@click.option('--name', prompt="Product name", help="Product name")
@click.option('--description', prompt="Description", help="Product description")
def product_add(name, description):
    """Add new product to Defect Dojo

    :param name: Product name
    :param description: Product description

    """

    dojo_connector = connector.Connector()

    product_type = 1 # TODO: How can we use it?
    product = dojo_connector.dd_v2.create_product(name, description, product_type)

# @click.option('--action', default='add_product', help='What you want to perform')

# TODO: how to delete?
@main.command()
def product_delete_all():
    """Delete all products

    """
    dojo_connector = connector.Connector()

    products = dojo_connector.dd_v1.list_products()
    print(products.data_json(pretty=True))
    for product in products:
        dojo_connector.dd_v1.delete

if __name__ == '__main__':
    main()
