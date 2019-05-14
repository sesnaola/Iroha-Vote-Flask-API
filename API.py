import os
import binascii
import sys
from iroha import Iroha, IrohaCrypto, IrohaGrpc
from iroha.primitive_pb2 import can_set_my_account_detail

from flask import jsonify
from flask import Flask
from flask_cors import CORS, cross_origin
app = Flask(__name__)
cors = CORS(app, resorces={r'/d/*': {"origins": '*'}})

if sys.version_info[0] < 3:
    raise Exception('Python 3 or a more recent version is required.')

IROHA_HOST_ADDR = os.getenv('IROHA_HOST_ADDR', '192.168.1.49')
IROHA_PORT = os.getenv('IROHA_PORT', '50051')
ADMIN_ACCOUNT_ID = os.getenv('ADMIN_ACCOUNT_ID', 'admin@test')
ADMIN_PRIVATE_KEY = os.getenv(
    'ADMIN_PRIVATE_KEY', 'f101537e319568c765b2cc89698325604991dca57b9716b58016b253506cab70')
user_private_key = IrohaCrypto.private_key()
user_public_key = IrohaCrypto.derive_public_key(user_private_key)
iroha = Iroha(ADMIN_ACCOUNT_ID)
net = IrohaGrpc('{}:{}'.format(IROHA_HOST_ADDR, IROHA_PORT))


@app.route("/add_asset/<string:name>/<string:domain>/<int:precision>/")
def add_asset(name, domain, precision):

    commands = [iroha.command('CreateAsset', asset_name=name,
                              domain_id=domain, precision=2)
                ]
    tx = IrohaCrypto.sign_transaction(
        iroha.transaction(commands), ADMIN_PRIVATE_KEY)
    return jsonify(send_transaction_and_print_status(tx))


@app.route("/add_domain/<string:domain>/<string:role>/")
def add_domain(domain, role):

    commands = [iroha.command(
        'CreateDomain', domain_id=domain, default_role=role)]
    tx = IrohaCrypto.sign_transaction(
        iroha.transaction(commands), ADMIN_PRIVATE_KEY)
    return send_transaction_and_print_status(tx)


@app.route("/add_account/<string:name>/<string:domain>/")
def add_account(name, domain):

    tx = iroha.transaction([
        iroha.command('CreateAccount', account_name=name, domain_id=domain,
                      public_key=user_public_key)
    ])
    IrohaCrypto.sign_transaction(tx, ADMIN_PRIVATE_KEY)
    return send_transaction_and_print_status(tx)


@app.route("/add_vote_to_admin/<string:name>/<string:domain>/<string:amount>/")
def add_vote_to_admin(name, domain, amount):

    tx = iroha.transaction([
        iroha.command('AddAssetQuantity',
                      asset_id=name+'#'+domain, amount=amount)
    ])
    IrohaCrypto.sign_transaction(tx, ADMIN_PRIVATE_KEY)
    return send_transaction_and_print_status(tx)


@app.route("/get_user_details/<string:name>/<string:domain>/")
def get_user_details(name, domain):

    query = iroha.query('GetAccountDetail', account_id=name+'@'+domain)
    IrohaCrypto.sign_query(query, ADMIN_PRIVATE_KEY)

    response = net.send_query(query)
    data = response.account_detail_response
    return jsonify('Account id = {}, details = {}'.format(name+'@'+domain, data.detail))


@app.route("/get_asset_info/<string:name>/<string:domain>/")
def get_asset_info(name, domain):

    query = iroha.query('GetAssetInfo', asset_id=name+'#'+domain)
    IrohaCrypto.sign_query(query, ADMIN_PRIVATE_KEY)

    response = net.send_query(query)
    data = response.asset_response.asset

    return jsonify('Asset id = {}, precision = {}'.format(data.asset_id, data.precision))


@app.route("/get_account_assets/<string:name>/<string:domain>/")
def get_account_assets(name, domain):

    query = iroha.query('GetAccountAssets', account_id=name+'@'+domain)
    IrohaCrypto.sign_query(query, ADMIN_PRIVATE_KEY)

    response = net.send_query(query)
    data = response.account_assets_response.account_assets
    for asset in data:
        return jsonify('id = {}, balance = {}'.format(asset.asset_id, asset.balance))


@app.route("/transfer_vote_from_admin_to_user/<string:aName>/<string:aDomain>/<string:uName>/<string:uDomain>/<string:assetName>/<string:assetDomain>/<string:amount>/")
def transfer_vote_from_admin_to_user(aName, aDomain, uName, uDomain, assetName, assetDomain, amount):
    tx = iroha.transaction([
        iroha.command('TransferAsset', src_account_id=aName+'@'+aDomain, dest_account_id=uName+'@'+uDomain,
                      asset_id=assetName+'#'+assetDomain, description='transfer asset', amount=amount)
    ])
    IrohaCrypto.sign_transaction(tx, ADMIN_PRIVATE_KEY)
    return send_transaction_and_print_status(tx)

# -----------------------------------------------------------------
# "Helpers"
# ----------------------------------------------------------------


def trace(func):
    """
    A decorator for tracing methods' begin/end execution points
    """

    def tracer(*args, **kwargs):
        name = func.__name__
        print('\tEntering "{}"'.format(name))
        result = func(*args, **kwargs)
        print('\tLeaving "{}"'.format(name))
        return result

    return tracer


@trace
def send_transaction_and_print_status(transaction):
    hex_hash = binascii.hexlify(IrohaCrypto.hash(transaction))
    print('Transaction hash = {}, creator = {}'.format(
        hex_hash, transaction.payload.reduced_payload.creator_account_id))
    net.send_tx(transaction)
    for status in net.tx_status_stream(transaction):
        return jsonify(status)


if __name__ == "__main__":
    app.run()
