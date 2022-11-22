import sys
import hashlib
import json

from time import time
from uuid import uuid4

from flask import Flask
from flask.globals import request
from flask.json import jsonify

import requests
from urllib.parse import urlparse

from flask_pymongo import PyMongo
from flask_cors import CORS, cross_origin

import datetime

def myconverter(o):
    if isinstance(o, datetime.datetime):
        return o.__str__()
ip_countract = "localhost:5000"
class Blockchain(object):
    difficulty_target = "0000"

    def hash_block(self, block):
        block_encoded = json.dumps(block, sort_keys=True, default=myconverter).encode()
        return hashlib.sha256(block_encoded).hexdigest()

    def __init__(self, init=False):
        self.nodes = set()
        self.chain = []

        self.current_transaction = []

        genesis_hash = self.hash_block("hashing_block_pertama")
        
        if init:
            self.append_block(hash_of_previous_block = genesis_hash, nonce = self.proof_of_work(0, genesis_hash, []))

    def add_node(self, address):
        parse_url = urlparse(address)
        self.nodes.add(parse_url.netloc)
        print(parse_url.netloc)

    def valid_chain(self, chain):
        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]

            if block['hash_of_previous_block'] != self.hash_block(last_block):
                return False
        
            if not self.valid_proof(
                current_index,
                block['hash_of_previous_block'],
                block['transaction'],
                block['nonce']
            ):
                return False
            last_block = block
            current_index += 1
        
        return True

    def update_blockchain(self):
        neighbours = self.nodes
        new_chain = None

        max_length = len(self.chain)

        for node in neighbours:
            response = requests.get(f'http://{node}/blockchain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

                if new_chain:
                    self.chain = new_chain
                    return True
            
        return False


    def proof_of_work(self, index, hash_of_previous_block, transaction):
        nonce = 0

        while self.valid_proof(index, hash_of_previous_block, transaction, nonce) is False:
            nonce += 1
        return nonce

    def valid_proof(self, index, hash_of_previous_block, transaction, nonce):
        content = f'{index}{hash_of_previous_block}{transaction}{nonce}'.encode()

        content_hash = hashlib.sha256(content).hexdigest()

        return content_hash[:len(self.difficulty_target)] == self.difficulty_target

    def append_block(self, nonce, hash_of_previous_block, init=False):
        block = {
            '_id' : len(self.chain),
            'index' : len(self.chain),
            'timestamp' : time(),
            'transaction' : self.current_transaction,
            'nonce' : nonce,
            'hash_of_previous_block' : hash_of_previous_block,
            'mined_by' : node_identifier
        }

        self.current_transaction = []
        self.chain.append(block)

        currentCollection = mongo.db.history_access
        currentCollection.insert_one(block)

        return block

    def add_transaction(self, sender, recipient, doc_type, access, owner_id, doc_id):
        self.current_transaction.append({
            'sender' : sender,
            'recipient' : recipient,
            'doc_type' : doc_type,
            'access' : access,
            'owner_id':owner_id,
            'doc_id':doc_id,
            'datetime': datetime.datetime.now()
        })
        return self.last_block['index'] + 1

    @property
    def last_block(self):
        return self.chain[-1]

app = Flask(__name__)
cors = CORS(app)
app.config['MONGO_URI'] = 'mongodb://localhost:27017/history_access'
app.config['CORS_Headers'] = 'Content-Type'
mongo = PyMongo(app)

node_identifier = str(uuid4()).replace("-","")

# blockchain = mongo.db.history_access.find()
# print(blockchain)
# chain = []
# for doc in blockchain:
#     chain.append(doc)

# if len(chain) == 0:
#     blockchain = Blockchain()
# else:
#     blockchain.chain = chain

blockchain = Blockchain()
temp_chain = mongo.db.history_access.find()
chain = []
for doc in temp_chain:
    chain.append(doc)
if len(chain) == 0:
    blockchain = Blockchain(True)
else:
    blockchain.chain = chain

#routes
@app.route('/blockchain', methods=['GET'])
def full_chain():
    response = {
        'chain' : blockchain.chain,
        'length' : len(blockchain.chain)
    }
    return jsonify(response), 200

@app.route('/mine', methods=['GET'])
def mine_block():
    # blockchain.add_transaction(
    #     sender = "0",
    #     recipient = node_identifier,
    #     amount = 1
    # )

    last_block_hash = blockchain.hash_block(blockchain.last_block)

    index = len(blockchain.chain)
    nonce = blockchain.proof_of_work(index, last_block_hash, blockchain.current_transaction)

    block = blockchain.append_block(nonce, last_block_hash)

    response = {
        'message' : "Block baru telah ditambahkan (mined)",
        'index' : block['index'],
        'hash_of_previous_block' : block['hash_of_previous_block'],
        'nonce' : block['nonce'],
        'transaction' : block['transaction']
    }

    return jsonify(response), 200

@app.route('/transaction/new', methods=['POST'])
def new_transaction():
    values = request.get_json()

    required_fields = ['sender', 'recipient', 'doc_type', 'access', 'owner_id', 'doc_id']
    if not all(k in values for k in required_fields):
        return ("Missing fields", 400)
    
    index = blockchain.add_transaction(
        values['sender'],
        values['recipient'],
        values['doc_type'],
        values['access'],
        values['owner_id'], 
        values['doc_id']
    )
    if len(blockchain.current_transaction) >= 1:
        mine_block()
    response = {'message': f'Riwayat telah ditambahkan ke block {index}'}

    return (jsonify(response), 201)

@app.route('/nodes/add_nodes', methods=['POST'])
def add_nodes():
    values = request.get_json()
    nodes = values.get('nodes')

    if nodes is None:
        return "Error, missing node(s) info", 400

    for node in nodes:
        blockchain.add_node(node)

    response = {
        'message' : "Node baru telah ditambahkan",
        'nodes' : list(blockchain.nodes)
    }

    return jsonify(response), 200

@app.route('/nodes/sync', methods=['GET'])
def sync():
    updated = blockchain.update_blockchain()
    if updated:
        response = {
            'message' : "Blockchain telah diupdate dengan data terbaru",
            'blockchain' : blockchain.chain
        }
    else:
        response = {
            'message' : "Blockchain sudah menggunakan data paling baru",
            'blockchain' : blockchain.chain
        }
    
    return jsonify(response), 200

@app.route('/check_access', methods=['GET'])
def check_access():
    values = request.get_json()

    required_fields = ['sender', 'recipient', 'doc_type', 'owner_id']
    if not all(k in values for k in required_fields):
        return ("Missing fields", 400)
    
    currentCollection = mongo.db.history_access
    holder = list()
    datas = currentCollection.find({'transaction.sender':values['sender'], 'transaction.recipient':values['recipient'], 'transaction.doc_type':values['doc_type']})
    for i,data in enumerate(datas):
        holder.append(data['transaction'])

    response = holder[-1][-1]
    return jsonify(response), 200

@app.route('/count_access', methods=['GET'])
def count_access():
    values = request.get_json()

    required_fields = ['owner_id']
    if not all(k in values for k in required_fields):
        return ("Missing fields", 400)

    currentCollection = mongo.db.history_access
    holder = list()
    datas = currentCollection.find({'transaction.sender':values['owner_id'], 'transaction.owner_id':values['owner_id']})

    for i,data in enumerate(datas):
        holder.append(data['transaction'])
    
    flatten_list = [j for sub in holder for j in sub]

    # print(flatten_list)

    
    list_dict = {}
    response = {}
    for i in range(len(flatten_list)):
        if flatten_list[i]['doc_type'] in list_dict:
            if flatten_list[i]['sender'] == flatten_list[i]['owner_id']:
                if flatten_list[i]['access'] == 1:
                    list_dict[flatten_list[i]['doc_type']]['1'].append(flatten_list[i]['recipient'])
                if flatten_list[i]['access'] == 0:
                    list_dict[flatten_list[i]['doc_type']]['0'].append(flatten_list[i]['recipient'])
                if flatten_list[i]['access'] == -1 and (flatten_list[i]['recipient'] in list_dict[flatten_list[i]['doc_type']]['1']):
                    list_dict[flatten_list[i]['doc_type']]['1'].remove(flatten_list[i]['recipient'])
        else:
            list_dict[flatten_list[i]['doc_type']] = {'1':[],'0':[]}
            response[flatten_list[i]['doc_type']] = {'1':[],'0':[]}
            if flatten_list[i]['sender'] == flatten_list[i]['owner_id']:
                if flatten_list[i]['access'] == 1:
                    list_dict[flatten_list[i]['doc_type']]['1'].append(flatten_list[i]['recipient'])
                if flatten_list[i]['access'] == 0:
                    list_dict[flatten_list[i]['doc_type']]['0'].append(flatten_list[i]['recipient'])
    
    # print(list_dict)
    for k, v in list_dict.items():
        response[k]['1'] = len(v['1'])
        response[k]['0'] = len(v['0'])

    return jsonify(response), 200

@app.route('/count_access_by_doc', methods=['GET'])
def count_access_by_doc_id():
    values = request.get_json()
    print(values)
    required_fields = ['doc_id']
    if not all(k in values for k in required_fields):
        return ("Missing fields", 400)

    currentCollection = mongo.db.history_access
    holder = list()
    datas = currentCollection.find({'transaction.doc_id':values['doc_id']})

    for i,data in enumerate(datas):
        holder.append(data['transaction'])
    
    flatten_list = [j for sub in holder for j in sub]

    # print(flatten_list)
    list_dict = {}
    response = {}
    for i in range(len(flatten_list)):
        if flatten_list[i]['doc_type'] in list_dict:
            if flatten_list[i]['sender'] == flatten_list[i]['owner_id']:
                if flatten_list[i]['access'] == 1:
                    list_dict[flatten_list[i]['doc_type']]['1'].append(flatten_list[i]['recipient'])
                if flatten_list[i]['access'] == 0:
                    list_dict[flatten_list[i]['doc_type']]['0'].append(flatten_list[i]['recipient'])
                if flatten_list[i]['access'] == -1 and (flatten_list[i]['recipient'] in list_dict[flatten_list[i]['doc_type']]['1']):
                    list_dict[flatten_list[i]['doc_type']]['1'].remove(flatten_list[i]['recipient'])
        else:
            list_dict[flatten_list[i]['doc_type']] = {'1':[],'0':[]}
            response[flatten_list[i]['doc_type']] = {'1':[],'0':[]}
            if flatten_list[i]['sender'] == flatten_list[i]['owner_id']:
                if flatten_list[i]['access'] == 1:
                    list_dict[flatten_list[i]['doc_type']]['1'].append(flatten_list[i]['recipient'])
                if flatten_list[i]['access'] == 0:
                    list_dict[flatten_list[i]['doc_type']]['0'].append(flatten_list[i]['recipient'])
    
    # print(list_dict)
    for k, v in list_dict.items():
        response[k]['1'] = len(v['1'])
        response[k]['0'] = len(v['0'])

    return jsonify(response), 200

@app.route('/dokumen/<doc_id>', methods=['GET'])
def list_access(doc_id):

    if doc_id == None:
        return ("Missing fields", 400)

    currentCollection = mongo.db.history_access
    holder = list()
    datas = currentCollection.find({'transaction.doc_id':int(doc_id), 'transaction.access':1})
    
    for i,data in enumerate(datas):
        holder.append(data['transaction'])
    
    flatten_list = [j for sub in holder for j in sub]

    list_recipients = []
    list_date = []
    list_name = []

    for i in range(len(flatten_list)):
        list_recipients.append(flatten_list[i]["recipient"])
        list_date.append(flatten_list[i]["datetime"])
        data = requests.get(f'http://{ip_countract}/user/{int(flatten_list[i]["recipient"])}')
        print(data)
        list_name.append(data.json()["name"])

    response = []

    for i in range(len(list_name)):
        temp = {
            'nama_pengakses':list_name[i],
            'tanggal':list_date[i].strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        }
        response.append(temp)
        
    return jsonify(response), 200

@app.route('/get_access/user/<id>', methods=['GET'])
def get_access_by_id_usr(id):
    if id == None:
        return ("Missing fields", 400)

    currentCollection = mongo.db.history_access
    holder = list()
    datas = currentCollection.find({'transaction.owner_id':int(id)})

    for i,data in enumerate(datas):
        holder.append(data['transaction'])
    
    flatten_list = [j for sub in holder for j in sub]
    for i in range(len(flatten_list)):
        flatten_list[i]['datetime'] = flatten_list[i]['datetime'].strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return jsonify(flatten_list), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(sys.argv[1]), debug=True)