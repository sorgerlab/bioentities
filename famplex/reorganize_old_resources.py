# -*- coding: utf-8 -*-

"""This script upgrades all of the FamPlex CSV files."""

import csv
import json
import os
import time
from collections import Counter
from operator import itemgetter
from typing import Tuple

from famplex.constants import (
    ENTITIES_PATH, EQUIVALENCES_PATH, GROUNDING_MAP_PATH, METADATA_PATH,
    RELATIONS_PATH,
)
from indra.databases import chebi_client, go_client, hgnc_client, mesh_client, mirbase_client, uniprot_client

HERE = os.path.abspath(os.path.dirname(__file__))

# Input paths
INPUT_RESOURCES = os.path.join(HERE, os.pardir)
ENTITIES_CSV_PATH = os.path.join(INPUT_RESOURCES, 'entities.csv')
EQUIVALENCES_CSV_PATH = os.path.join(INPUT_RESOURCES, 'equivalences.csv')
GROUNDING_MAP_CSV_PATH = os.path.join(INPUT_RESOURCES, 'grounding_map.csv')
RELATIONS_CSV_PATH = os.path.join(INPUT_RESOURCES, 'relations.csv')
DESCRIPTIONS_CSV_PATH = os.path.join(INPUT_RESOURCES, 'descriptions.csv')

FAMPLEX_DESCRIPTION = 'A protein family, complex, family of complexes,or complex of families'

client_id_lookups = [
    ('HGNC', hgnc_client.get_hgnc_id),
]

client_name_lookups = [
    ('UP', uniprot_client.get_mnemonic),
    ('GO', go_client.get_go_label),
    ('MESH', mesh_client.get_mesh_name),
    ('MIRBASE', mirbase_client.get_mirbase_name_from_mirbase_id),
    ('CHEBI', chebi_client.get_chebi_name_from_id),
]


def main():
    fplx_name_to_id = {}

    def get_id_label(db: str, db_id: str) -> Tuple[str, str]:
        if db == 'FPLX':
            return fplx_name_to_id[db_id], db_id

        for client, lookup in client_id_lookups:
            if db == client:
                return lookup(db_id), db_id

        for client, lookup in client_name_lookups:
            if db == client:
                return db_id, lookup(db_id)

        else:
            return db_id, ''

    with open('descriptions.csv') as in_file:
        reader = csv.reader(
            in_file,
            delimiter=',',
            lineterminator='\r\n',
            quoting=csv.QUOTE_MINIMAL,
            quotechar='"',
        )
        fplx_name_to_description = {
            fplx_name: (
                description,
                [r.strip() for r in references.split(';')],
            )
            for fplx_name, references, description in reader
        }

    with open('entities.csv') as in_file, open(ENTITIES_PATH, 'w') as out_file:
        writer = csv.writer(
            out_file,
            delimiter=',',
            quotechar='"',
            quoting=csv.QUOTE_MINIMAL,
            lineterminator='\r\n',
        )
        for i, fplx_name in enumerate(in_file, start=1):
            fplx_name = fplx_name.strip()
            fplx_id = fplx_name_to_id[fplx_name] = f'{i:06}'
            description, references = fplx_name_to_description.get(fplx_name, (None, None))
            writer.writerow((
                fplx_id,
                fplx_name,
                description if description is not None else '',
                ','.join(references) if references is not None else '',
            ))

    with open('equivalences.csv') as in_file, open(EQUIVALENCES_PATH, 'w') as out_file:
        # print('xref_db', 'xref_id', 'fplx_id', 'fplx_name', sep='\t', file=out_file)
        reader = csv.reader(
            in_file,
            delimiter=',',
            lineterminator='\r\n',
            quoting=csv.QUOTE_MINIMAL,
            quotechar='"',
        )
        writer = csv.writer(
            out_file,
            delimiter=',',
            quotechar='"',
            quoting=csv.QUOTE_MINIMAL,
            lineterminator='\r\n',
        )
        for xref_db, xref_name, fplx_name in reader:
            writer.writerow((
                xref_db,
                xref_name,
                fplx_name_to_id[fplx_name],
                fplx_name,
            ))

    groundings_unlabelled = set()
    with open('grounding_map.csv') as in_file, open(GROUNDING_MAP_PATH, 'w') as out_file:
        reader = csv.reader(
            in_file,
            delimiter=',',
            lineterminator='\r\n',
            quoting=csv.QUOTE_MINIMAL,
            quotechar='"',
        )
        writer = csv.writer(
            out_file,
            delimiter=',',
            quotechar='"',
            quoting=csv.QUOTE_MINIMAL,
            lineterminator='\r\n',
        )
        for text, *line in reader:
            for xref_db, identifier in zip(line[::2], line[1::2]):
                if not xref_db or not identifier:
                    continue

                identifier, xref_name = get_id_label(xref_db, identifier)
                if not xref_name:
                    groundings_unlabelled.add((xref_db, identifier))

                writer.writerow((text, xref_db, identifier, xref_name))

    # Logging for unlabelled entities
    if groundings_unlabelled:
        print(f'\n{len(groundings_unlabelled)} groundings are unlabelled:')
        grounding_unlabelled_counter = Counter(map(itemgetter(0), groundings_unlabelled))
        s = max(map(len, grounding_unlabelled_counter))
        for xref_db, count in grounding_unlabelled_counter.most_common():
            print(f'{xref_db:>{s}s} unlabelled {count}')

    relations_unlabelled = set()
    with open('relations.csv') as in_file, open(RELATIONS_PATH, 'w') as out_file:
        # print('sub_db', 'sub_id', 'sub_name', 'rel',
        #      'obj_db', 'obj_id', 'obj_name', sep='\t', file=out_file)

        reader = csv.reader(
            in_file,
            delimiter=',',
            lineterminator='\r\n',
            quoting=csv.QUOTE_MINIMAL,
            quotechar='"',
        )
        writer = csv.writer(
            out_file,
            delimiter=',',
            quotechar='"',
            quoting=csv.QUOTE_MINIMAL,
            lineterminator='\r\n',
        )
        for sub_db, sub_id, rel, obj_db, obj_id in reader:
            sub_id, sub_name = get_id_label(sub_db, sub_id)
            if not sub_name:
                relations_unlabelled.add((sub_db, sub_id))

            obj_id, obj_name = get_id_label(obj_db, obj_id)
            if not obj_name:
                relations_unlabelled.add((obj_db, obj_id))

            writer.writerow((
                sub_db, sub_id, sub_name, rel,
                obj_db, obj_id, obj_name
            ))

    if relations_unlabelled:  # Logging for unlabelled entities
        print(f'\n{len(relations_unlabelled)} relations are unlabelled:')
        relations_unlabelled_counter = Counter(map(itemgetter(0), relations_unlabelled))
        s = max(map(len, relations_unlabelled_counter))
        for xref_db, count in relations_unlabelled_counter.most_common():
            print(f'{xref_db:>{s}s} unlabelled {count}')

    metadata = {
        'Time Exported': str(time.asctime()),
        'Unlabelled Groundings': [
            dict(db=db, db_id=db_id)
            for db, db_id in sorted(groundings_unlabelled)
        ],
        'Unlabelled Relations': [
            dict(db=db, db_id=db_id)
            for db, db_id in sorted(relations_unlabelled)
        ]
    }
    with open(METADATA_PATH, 'w') as file:
        json.dump(metadata, file, indent=2, sort_keys=True)


if __name__ == '__main__':
    main()
