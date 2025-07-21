from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random
import csv
from flask import Flask, request, render_template, Response
from io import StringIO
import base64

app = Flask(__name__)


def extract_amazon_products(url):
    options = Options()
    options.add_argument("--headless")
    options.set_preference("general.useragent.override",
                           "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    driver = webdriver.Firefox(options=options)
    driver.set_window_size(1366, 768)

    try:
        driver.get(url)
        time.sleep(random.uniform(2.0, 5.0))

        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-component-type='s-search-result']"))
            )
        except:
            if "captcha" in driver.page_source.lower():
                return {"error": "Amazon is showing CAPTCHA. Try again later or use proxies."}
            else:
                return {"error": "No products found. Amazon may have blocked the request."}

        products = driver.find_elements(By.CSS_SELECTOR, "div[data-component-type='s-search-result']")
        extracted_data = []

        for product in products[:20]:  # Limit to 20 products
            try:
                time.sleep(random.uniform(0.3, 1.2))
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", product)

                # Name extraction
                name = ""
                try:
                    name_element = product.find_element(By.CSS_SELECTOR, "h2 a.a-link-normal")
                    name = name_element.text.strip()
                except:
                    try:
                        name_element = product.find_element(By.CSS_SELECTOR, "h2 span")
                        name = name_element.text.strip()
                    except:
                        continue

                # Price extraction
                price = "Not available"
                try:
                    whole_price = product.find_element(By.CSS_SELECTOR, "span.a-price-whole").text
                    fraction_price = product.find_element(By.CSS_SELECTOR, "span.a-price-fraction").text
                    price = f"${whole_price}.{fraction_price}"
                except:
                    try:
                        price_element = product.find_element(By.CSS_SELECTOR, "span.a-offscreen")
                        price = price_element.get_attribute("textContent").strip()
                    except:
                        try:
                            price_element = product.find_element(By.CSS_SELECTOR, "span.a-color-base")
                            price = price_element.text.strip()
                        except:
                            pass

                # Rating and other info
                rating = "No rating"
                num_ratings = ""
                try:
                    rating_element = product.find_element(By.CSS_SELECTOR, "span.a-icon-alt")
                    rating = rating_element.get_attribute("textContent").split()[0]
                    num_ratings_element = product.find_element(By.CSS_SELECTOR, "span.a-size-base.s-underline-text")
                    num_ratings = num_ratings_element.text.strip()
                except:
                    pass

                # Image extraction
                image_url = ""
                try:
                    img_element = product.find_element(By.CSS_SELECTOR, "img.s-image")
                    image_url = img_element.get_attribute("src")
                except:
                    pass

                extracted_data.append({
                    'name': name,
                    'price': price,
                    'rating': rating,
                    'num_ratings': num_ratings,
                    'image_url': image_url,
                    'url': url
                })

            except Exception as e:
                continue

        return {"products": extracted_data}

    except Exception as e:
        return {"error": f"An error occurred: {str(e)[:100]}..."}

    finally:
        driver.quit()


@app.route('/', methods=['GET', 'POST'])
def index():
    theme = request.cookies.get('theme', 'light')
    if request.method == 'POST':
        url = request.form.get('url', '').strip()
        if not url.startswith('https://www.amazon.com/'):
            return render_template('index.html', error="Please enter a valid Amazon product search URL", theme=theme)

        result = extract_amazon_products(url)

        if 'error' in result:
            return render_template('index.html', error=result['error'], theme=theme)

        return render_template('index.html',
                               products=result['products'],
                               url=url,
                               theme=theme)

    return render_template('index.html', theme=theme)


@app.route('/download')
def download():
    url = request.args.get('url', '')
    if not url:
        return "No URL provided", 400

    result = extract_amazon_products(url)
    if 'error' in result:
        return result['error'], 400

    # Generate CSV in memory
    csv_data = StringIO()
    fieldnames = ['name', 'price', 'rating', 'num_ratings', 'image_url', 'url']
    csv_writer = csv.DictWriter(csv_data, fieldnames=fieldnames)
    csv_writer.writeheader()
    csv_writer.writerows(result['products'])
    csv_data.seek(0)

    return Response(
        csv_data.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=amazon_products.csv"}
    )


@app.route('/toggle_theme')
def toggle_theme():
    theme = request.cookies.get('theme', 'light')
    new_theme = 'dark' if theme == 'light' else 'light'
    response = app.make_response(render_template('index.html', theme=new_theme))
    response.set_cookie('theme', new_theme)
    return response


if __name__ == '__main__':
    app.run(debug=True)
