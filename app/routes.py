from app import app
from app import utils
import pandas as pd
import numpy as np
import os
import io as io
import json
import requests
from bs4 import BeautifulSoup
from matplotlib import pyplot as plt
from flask import render_template, request, redirect, url_for, send_file, send_from_directory

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/extract', methods=['POST','GET'])
def extract():
    if request.method == 'POST':
        product_id = request.form.get('product_id')
        url = f"https://www.ceneo.pl/{product_id}"
        response = requests.get(url)
        if response.status_code == requests.codes['ok']:
            page_dom = BeautifulSoup(response.text, "html.parser")
            opinions_count = utils.extract(page_dom, "a.product-review__link > span")
            if opinions_count:
                product_name = utils.extract(page_dom, "h1")
                url = f"https://www.ceneo.pl/{product_id}#tab=reviews"
                all_opinions = []
                while (url):
                    response = requests.get(url)
                    page_dom = BeautifulSoup(response.text, "html.parser")
                    opinions = page_dom.select("div.js_product-review")
                    for opinion in opinions:
                        single_opinion = {
                            key: utils.extract(opinion, *value)
                                for key, value in utils.selectors.items()
                        }
                        all_opinions.append(single_opinion)
                    try:
                        url = "https://www.ceneo.pl" + utils.extract(page_dom,"a.pagination__next",'href')
                    except TypeError:
                        url = None
                    if not os.path.exists("app/data"):
                        os.mkdir("app/data")
                    if not os.path.exists("app/data/opinions"):
                        os.mkdir("app/data/opinions")
                    with open(f"app/data/opinions/{product_id}.json", "w", encoding="UTF-8") as opf:
                        json.dump(all_opinions, opf,indent=4, ensure_ascii=False)
                    opinions = pd.DataFrame.from_dict(all_opinions)
                    opinions.rating = opinions.rating.apply(lambda rate: rate.split("/")[0].replace(",",".")).astype(float)
                    product = {
                    'product_id' : product_id,
                    'product_name' : product_name,
                    'opinions_count' : opinions.shape[0],
                    'pros_count' : int(opinions.pros.astype(bool).sum()),
                    'cons_count' : int(opinions.cons.astype(bool).sum()),
                    'average_rating' : round(opinions.rating.mean(),2),
                    'rating_distribution' : opinions.rating.value_counts().reindex(np.arange(0,5.5,0.5), fill_value = 0.0).to_dict(),
                    'recommendation_distribution' : opinions.recommendation.value_counts(dropna=False).reindex(["Polecam","Nie polecam",None]).to_dict(),
                    'total_opinions' : len(opinions)
                    }
                    if not os.path.exists("app/data"):
                        os.mkdir("app/data")
                    if not os.path.exists("app/data/products"):
                        os.mkdir("app/data/products")
                    with open(f"app/data/products/{product_id}.json", "w", encoding="UTF-8") as opf:
                        json.dump(product, opf,indent=4, ensure_ascii=False)
                #proces ekstrakcji
                return redirect(url_for('product', product_id=product_id))
            return render_template("extract.html", error="Dla produktu o podanym kodzie nie ma opinii")
        return render_template("extract.html", error="Produkt o podanym kodzie nie istnieje")
    return render_template("extract.html")

@app.route('/products')
def products():
    products_list = [filename.split(".")[0] for filename in os.listdir("app/data/opinions")]
    products = []
    for product_id in products_list:
        with open(f"app/data/products/{product_id}.json", "r", encoding="UTF-8") as opf:
            products.append(json.load(opf))
    
    return render_template("products.html", products = products, enumerate=enumerate)

@app.route('/author')
def author():
    return render_template("author.html")

@app.route('/product/<product_id>')
def product(product_id):
    file_path = f"app/data/opinions/{product_id}.json"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="UTF-8") as file:
            opinions = json.load(file)
            # przygotowanie opinii, żeby było łatwiej je sortować, filtrować
            for opinion in opinions:
                for key, value in opinion.items():
                    if isinstance(value, str):
                        opinion[key] = value.lower()
                    elif value is None:
                        opinion[key] = "0"
            recommendation_options = set(opinion.get('recommendation') for opinion in opinions)
            recommendation_options = [option for option in recommendation_options if option is not None]
            recommendation_options.sort()
    else:
        opinions = []
        recommendation_options = []

    recommendation_option = request.args.get('recommendation_option', 'all')

    # wstępne filtrowanie opini xD
    if recommendation_option == 'polecam':
        opinions = [opinion for opinion in opinions if opinion.get('recommendation') == 'polecam']
    elif recommendation_option == 'nie polecam':
        opinions = [opinion for opinion in opinions if opinion.get('recommendation') == 'nie polecam']
    elif recommendation_option == '0':
        opinions = [opinion for opinion in opinions if opinion.get('recommendation') == '0']

    sort_by = request.args.get('sort_by', 'rating')
    order = request.args.get('order', 'asc')

    sorted_opinions = sorted(opinions, key=lambda x: x.get(sort_by, ''), reverse=(order == 'desc'))
    total_opinions = len(sorted_opinions)

    return render_template("product.html", opinions=sorted_opinions, enumerate=enumerate, total_opinions=total_opinions, list=list, product_id=product_id, sort_by=sort_by, order=order, recommendation_options=recommendation_options)

@app.route('/product/download_json/<product_id>')
def download_json(product_id):
    return send_file(f"data/opinions/{product_id}.json", "text/json", as_attachment=True)
    
@app.route('/product/download_csv/<product_id>')
def download_csv(product_id):
    opinions = pd.read_json(f"app/data/opinions/{product_id}.json")
    buffer = io.BytesIO(opinions.to_csv(sep=";",decimal=",",).encode())
    return send_file(buffer, f"data/opinions/{product_id}.csv", "text/csv", download_name=f"{product_id}.csv")

@app.route('/product/download_xlsx/<product_id>')
def download_xlsx(product_id):
    pass

@app.route('/graphs/<product_id>')
def graphs(product_id):
    opinions = pd.read_json(f"app/data/opinions/{product_id}.json")
    opinions_df = pd.DataFrame(opinions)
    opinions_df.rating = opinions_df.rating.apply(lambda rate: rate.split("/")[0].replace(",", ".")).astype(float)
    rating_distribution = opinions_df.rating.value_counts().reindex(np.arange(0, 5.5, 0.5), fill_value=0.0)
    fig, ax = plt.subplots()
    rating_distribution.plot.bar(color="hotpink", ax=ax)
    plt.xticks(rotation=0)
    plt.xlabel("Liczba gwiazdek")
    plt.ylabel("Liczba opinii")
    plt.title("Histogram częstości ocen w opiniach")
    ax.bar_label(ax.containers[0], label_type="edge", fmt=lambda x: int(x) if x > 0 else "")
    chart_path = f"app/data/charts/{product_id}_rating_distribution.png"
    if not os.path.exists("app/data"):
        os.mkdir("app/data")
    if not os.path.exists("app/data/charts"):
        os.mkdir("app/data/charts")
    fig.savefig(chart_path)
    plt.close(fig)
    recommendation_distribution = opinions_df.recommendation.value_counts(dropna=False).reindex(["Polecam", "Nie polecam", None], fill_value=0)
    fig, ax = plt.subplots()
    recommendation_distribution.plot.pie(
        ax=ax,
        label="",
        colors=["seagreen", "palevioletred", "thistle"],
        labels=["Polecam", "Nie polecam", "Nie mam zdania"],
        autopct='%1.1f%%'
    )
    plt.title("Histogram udziału rekomendacji w opiniach")
    pie_chart_path = f"app/data/charts/{product_id}_recommendation_distribution.png"
    fig.savefig(pie_chart_path)
    plt.close(fig)
    return render_template("graphs.html", enumerate=enumerate, chart_path=chart_path, product_id=product_id)

@app.route('/charts/<filename>')
def get_chart(filename):
    return send_from_directory('data/charts', filename)