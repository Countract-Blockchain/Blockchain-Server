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


class Blockchain(object):
    difficulty_target = "0000"

    def hash_block(self, block):
        block_encoded = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_encoded).hexdigest()

    def __init__(self):
        self.nodes = set()
        self.chain = []

        self.current_transaction = []

        genesis_hash = self.hash_block("hashing_block_pertama")

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

    def append_block(self, nonce, hash_of_previous_block):
        block = {
            '_id' : len(self.chain)+1,
            'index' : len(self.chain)+1,
            'timestamp' : time(),
            'transaction' : self.current_transaction,
            'nonce' : nonce,
            'hash_of_previous_block' : hash_of_previous_block,
            'mined_by' : node_identifier
        }

        self.current_transaction = []
        self.chain.append(block)
        return block

    def add_transaction(self, sender, recipient, doc_type,access):
        self.current_transaction.append({
            'sender' : sender,
            'recipient' : recipient,
            'doc_type' : doc_type,
            'access' : access
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
    blockchain = Blockchain()
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

    currentCollection = mongo.db.history_access
    currentCollection.insert_one(block)

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

    required_fields = ['sender', 'recipient', 'doc_type', 'access']
    if not all(k in values for k in required_fields):
        return ("Missing fields", 400)
    
    index = blockchain.add_transaction(
        values['sender'],
        values['recipient'],
        values['doc_type'],
        values['access']
    )

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(sys.argv[1]))