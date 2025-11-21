import runpod

import sys
import os
from pathlib import Path


def handler(event):    
    # base_path = r"D:\Git_Clone\GeneExp"
    # sys.path.append(str(Path(base_path)))
    from main.generate_tags import collect_tags
    from main.esm_embedding import embed_sequences

    print(f"Worker Start")
    data = event
    
    file_name = data['input'].get('file_name', None)
    organism = data['input'].get('organism', None)
    strain = data['input'].get('strain', "")
    sub_strain = data['input'].get('sub_strain', "")
    products = data['input'].get('products', [])
    translations = data['input'].get('translations', [])

    output_dir = "temp/"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    #########################################
    # Generate ESM2 embeddings
    tags = collect_tags(file_name, products, organism, strain, sub_strain, output_dir)
    embeddings = embed_sequences(file_name, translations, output_dir)
    #########################################
        

    return {
        "status": "success",
        "message": f"Generated {len(tags)} tags for {len(embeddings)} sequences.",
        "tags": tags,
        "embeddings": embeddings
    }


if __name__ == '__main__':
    runpod.serverless.start({'handler': handler})
