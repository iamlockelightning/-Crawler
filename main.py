# coding=utf-8
import os
import json

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from bs4 import BeautifulSoup

import wget
import subprocess

import img2pdf
from PyPDF2 import PdfFileMerger



def get_file(browser, url, d_path):
    browser.get(url)
    html_page = browser.page_source
    soup = BeautifulSoup(html_page, "html.parser")
    yandex_url = ""
    for a in soup.select('a[class="downloadD"]'):
        yandex_url = a.get("href")[4:]
    print(yandex_url)

    browser.get("https://cloud-api.yandex.net/v1/disk/public/resources/download?public_key=" + yandex_url)
    html_page = browser.page_source
    soup = BeautifulSoup(html_page, "html.parser")
    down_href = json.loads(soup.text)["href"]
    print(down_href)
    # print("wget...")
    # wget.download(down_href, out="down/" + yandex_url.split("/")[-1] + ".zip")
    print("aria2c...") # faster than wget
    subprocess.run(["aria2c", "-d "+d_path, down_href])
    return (yandex_url, down_href)


def get_toms(browser, url):
    # current total page number is 10
    total_page_num = 10
    tom_url_cont = []
    for i in range(1, total_page_num + 1):
        print("parsing page:", i, ". total:", total_page_num)
        browser.get(url + "-"+str(i) if i != 1 else url)

        html_page = browser.page_source
        soup = BeautifulSoup(html_page, "html.parser")
        cur_pos = len(tom_url_cont)
        for div in soup.select('div[class="post_news"]'):
            tom_url_cont.append({"name": div.text.strip(), "url": "http://fan-naruto.ru" + div.a.get("href")})
        for ii, div in enumerate(soup.select('div[class="post_content"]')):
            tom_url_cont[cur_pos + ii]["content"] = div.text.strip()
    return tom_url_cont



if __name__ == "__main__":
    options = Options()
    options.add_argument("--headless")
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    browser = webdriver.Chrome(options=options) # Chrome # Edge # Safari # Firefox


    url = "http://fan-naruto.ru/load/manga/manga_van_pis_skachat_i_chitat_onlajn/61"
    
    # 1. get all Том's urls
    tom_url_cont = get_tom(browser, url)
    print(tom_url_cont)
    print("len(tom_url_cont):", len(tom_url_cont))
    with open("tom_url_cont.txt", "w") as fw:
        for item in tom_url_cont:
            fw.write(item["name"] + "\t" + item["url"] + "\t" + item["content"].replace("\t", " ").replace("\n", "哈") + "\n")


    # 2. download all zips from Yandex Disk
    down_path = "./down"
    if not os.path.exists(down_path):
        os.mkdir(down_path)
    with open("tom_yandex.url.txt", "r") as fr:
        pass_set = set([x.split("\t")[0] for x in fr.read().strip().split("\n")])
    with open("tom_url_cont.txt", "r") as fr, open("tom_yandex.url.txt", "w") as fw:
        for i, line in enumerate(fr):
            tom_name, tom_url, tom_content = line.strip().split("\t")
            if tom_name in pass_set:
                print("pass...", tom_name)
                continue
            print("downloading:", tom_name, ". s_no:", i)
            hrefs = get_file(browser, tom_url, down_path)
            fw.write(tom_name + "\t" + "\t".join(hrefs) + "\n")


    # 3. unzip / unrar
    for filename in os.listdir(down_path):
        if filename.endswith(".zip"):
            subprocess.run(["ditto", "-V", "-x", "-k", "--sequesterRsrc", down_path + "/" + filename, down_path])
        elif " " in filename:
            rars = [x for x in os.listdir(down_path + "/" + filename) if x.endswith(".rar")]
            for rar in rars:
                subprocess.run(["unrar", "x", down_path+"/"+filename+"/"+rar, down_path+"/"+filename])


    # 4. check if all is ready
    toms = sorted([x for x in os.listdir(down_path) if "." not in x], key=lambda x: int(x.split(" ")[1]))
    print(toms)
    print("len(toms):", len(toms))
    assert len(toms) == max([int(x.split(" ")[1]) for x in toms])
    total_juans = []
    tom_juan_dict = {}
    for i, tom in enumerate(toms):
        juans = sorted([x for x in os.listdir(down_path+"/"+tom) if os.path.isdir(down_path+"/"+tom+"/"+x)], key=lambda x: int(x))
        if int(juans[-1]) - int(juans[0]) + 1 != len(juans):
            print(tom)
        if i != 0 and int(juans[0]) != int(total_juans[-1])+1:
            print(tom)
        total_juans += juans
        tom_juan_dict[tom] = juans
    print("len(total_juans):", len(total_juans))
    assert int(total_juans[-1])-int(total_juans[0])+1 == len(total_juans)

    
    # 5. convert jpg/png -> pdf -> concatenate all pages to one pdf
    output_path = "./output"
    if not os.path.exists(output_path):
        os.mkdir(output_path)
    for i, tom in enumerate(toms): # find ./down -name "*.pdf" -delete
        print(tom)
        pdf_files = []
        for j, juan in enumerate(tom_juan_dict[tom]):
            print("\t", juan)
            juan_path = down_path+"/"+tom+"/"+juan
            files = sorted([x for x in os.listdir(juan_path) if "fan-naruto.ru" in x and not x.endswith(".pdf") and not x.startswith(".")])
            
            for file in files:
                if file.startswith("backup_") or file.startswith("done_"):
                    continue
                try:
                    print("\t\t", file)
                    if "-" not in file.split("_")[0]:
                        # sips -s format [转换的目标格式] --out [目标文件名字] [输入文件]
                        tar_pdf = juan_path+"/"+ ".".join(file.split(".")[:-1]) + ".pdf"
                        subprocess.run(["sips", "-s", "format", "pdf", "--out", tar_pdf, juan_path+"/"+file])
                        pdf_files.append(tar_pdf)
                    else:
                        import cv2
                        img = cv2.imread(juan_path+"/"+file) # Read the image
                        print(img.shape)
                        if len(img.shape) == 2:
                            height, width = img.shape
                            width_cutoff = width // 2
                            s1, s2 = img[:, :width_cutoff], img[:, width_cutoff:]
                        else:
                            if img.shape[2] == 4:
                                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR) #convert the image from RGBA2RGB
                            height, width, channel = img.shape
                            width_cutoff = width // 2
                            s1, s2 = img[:, :width_cutoff, :], img[:, width_cutoff:, :]
                        s1_path = juan_path+"/"+file.split("_")[0].split("-")[1]+"_"+"_".join(file.split("_")[1:])
                        s2_path = juan_path+"/"+file.split("_")[0].split("-")[0]+"_"+"_".join(file.split("_")[1:])
                        cv2.imwrite(s1_path, s1)
                        cv2.imwrite(s2_path, s2)

                        s2_tar_pdf = ".".join(s2_path.split(".")[:-1]) + ".pdf"
                        subprocess.run(["sips", "-s", "format", "pdf", "--out", s2_tar_pdf, s2_path])
                        pdf_files.append(s2_tar_pdf)
                        s1_tar_pdf = ".".join(s1_path.split(".")[:-1]) + ".pdf"
                        subprocess.run(["sips", "-s", "format", "pdf", "--out", s1_tar_pdf, s1_path])
                        pdf_files.append(s1_tar_pdf)

                except Exception as e:
                    print("err...in", file, "\tE:", e)
                    a = input("press ctrl + c")
        
        merger = PdfFileMerger()
        print(pdf_files)
        for pdf in pdf_files:
            merger.append(pdf)
        merger.write(output_path+"/"+tom+".pdf")
        merger.close()
    

    print("__Done!")


    browser.close()
    browser.quit()
