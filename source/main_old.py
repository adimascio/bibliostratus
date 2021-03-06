# -*- coding: utf-8 -*-
"""
Created on Fri Oct 13 18:30:30 2017

@author: Etienne Cavalié

Programme de manipulations de données liées à la Transition bibliographique pour les bibliothèques françaises

"""

from lxml import etree
from urllib import request
import urllib.parse
from unidecode import unidecode
import urllib.error as error
import csv
import tkinter as tk
from tkinter import filedialog
from collections import defaultdict
import re
import webbrowser
import codecs
import json
import noticesbib2arkBnF as bib2ark
import noticesaut2arkBnF as aut2ark
import marc2tables as marc2tables
import ark2records as ark2records
import preferences

#import matplotlib.pyplot as plt

version = 1.06
lastupdate = "28/03/2018"
programID = "transbiblio"

ns = {"srw":"http://www.loc.gov/zing/srw/", "mxc":"info:lc/xmlns/marcxchange-v2", "m":"http://catalogue.bnf.fr/namespaces/InterXMarc","mn":"http://catalogue.bnf.fr/namespaces/motsnotices"}
nsSudoc = {"rdf":"http://www.w3.org/1999/02/22-rdf-syntax-ns#", "bibo":"http://purl.org/ontology/bibo/", "dc":"http://purl.org/dc/elements/1.1/", "dcterms":"http://purl.org/dc/terms/", "rdafrbr1":"http://rdvocab.info/RDARelationshipsWEMI/", "marcrel":"http://id.loc.gov/vocabulary/relators/", "foaf":"http://xmlns.com/foaf/0.1/", "gr":"http://purl.org/goodrelations/v1#", "owl":"http://www.w3.org/2002/07/owl#", "isbd":"http://iflastandards.info/ns/isbd/elements/", "skos":"http://www.w3.org/2004/02/skos/core#", "rdafrbr2":"http://RDVocab.info/uri/schema/FRBRentitiesRDA/", "rdaelements":"http://rdvocab.info/Elements/", "rdac":"http://rdaregistry.info/Elements/c/", "rdau":"http://rdaregistry.info/Elements/u/", "rdaw":"http://rdaregistry.info/Elements/w/", "rdae":"http://rdaregistry.info/Elements/e/", "rdam":"http://rdaregistry.info/Elements/m/", "rdai":"http://rdaregistry.info/Elements/i/", "sudoc":"http://www.sudoc.fr/ns/", "bnf-onto":"http://data.bnf.fr/ontology/bnf-onto/"}
nsisni = {'srw':'http://www.loc.gov/zing/srw/', 'dc':'http://purl.org/dc/elements/1.1/', 'diag':'http://www.loc.gov/zing/srw/diagnostic/', 'xcql':'http://www.loc.gov/zing/cql/xcql/'}
urlSRUroot = "http://catalogue.bnf.fr/api/SRU?version=1.2&operation=searchRetrieve&query="

chiffers = ["0","1","2","3","4","5","6","7","8","9"]
letters = ["a","b","d","e","f","g","h","i","j","k","l","m","n","o","p","q","r","s","t","u","v","w","x","y","z"]
punctuation = [".",",",";",":","?","!","%","$","£","€","#","\\","\"","&","~","{","(","[","`","\\","_","@",")","]","}","=","+","*","\/","<",">",")","}"]


errors = {
        "no_internet" : "Attention : Le programme n'a pas d'accès à Internet.\nSi votre navigateur y a accès, vérifiez les paramètres de votre proxy",
        "pb_input_utf8" : "Le fichier en entrée doit être en UTF-8 sans BOM.\nErreur d'encodage constatée",
        "pb_input_utf8_marcEdit" : """Erreur d'encodage constatée :
        Le fichier en entrée doit être en UTF-8 sans BOM.
        
        Si vous utilisez un fichier iso2709, convertissez-le d'abord en XML avec MarcEdit"""
        }

def click2openurl(url):
    webbrowser.open(url)
def annuler(master):
    master.destroy()

def check_last_compilation(programID):
    programID_last_compilation = 0
    display_update_button = False
    url = "https://raw.githubusercontent.com/Lully/bnf-sru/master/last_compilations.json"
    try:
        last_compilations = request.urlopen(url)
        reader = codecs.getreader("utf-8")
        last_compilations = json.load(reader(last_compilations))["last_compilations"][0]
        if (programID in last_compilations):
            programID_last_compilation = last_compilations[programID]
        if (programID_last_compilation > version):
            display_update_button = True
    except error.URLError:
        print("erreur réseau")
    return [programID_last_compilation,display_update_button]

def download_last_update(url="https://github.com/Transition-bibliographique/alignements-donnees-bnf/bin"):
    url = "https://github.com/Transition-bibliographique/alignements-donnees-bnf/tree/master/bin"
    webbrowser.open(url)

def check_access_to_network():
    access_to_network = True
    try:
        request.urlopen("http://www.bnf.fr")
    except error.URLError:
        print("Pas de réseau internet")
        access_to_network = False
    return access_to_network

def check_access2apis(i,dict_report):
    """Vérification de la disponibilité du SRU BnF et des API Abes
    (en supposant que si une requête d'exemple fonctionne, tout fonctionne"""
    testBnF = True
    testAbes = True
    testBnF = bib2ark.testURLretrieve("http://catalogue.bnf.fr/api/SRU?version=1.2&operation=searchRetrieve&query=bib.recordid%20all%20%2230000001%22&recordSchema=unimarcxchange&maximumRecords=20&startRecord=1")
    testAbes = bib2ark.testURLretrieve("https://www.sudoc.fr/services/isbn2ppn/0195141156")
    dict_report["testAbes"][i] = testAbes
    dict_report["testBnF"][i] = testBnF

        

def clean_string(string,replaceSpaces=False,replaceTirets=False):
    string = unidecode(string.lower())
    for sign in punctuation:
        string = string.replace(sign," ")
    string = string.replace("'"," ")
    if (replaceTirets == True):
        string = string.replace("-"," ")
    if (replaceSpaces == True):
        string = string.replace(" ","")
    string = ' '.join(s for s in string.split() if s != "")
    string = string.strip()
    return string

def RepresentsInt(s):
    try: 
        int(s)
        return True
    except ValueError:
        return False

def extract_subfield(record,field,subfield,nb_occ="all",sep="~"):
    path = ".//mxc:datafield[@tag='" + field + "']/mxc:subfield[@code='" + subfield + "']"
    listeValues = []
    if (nb_occ == "first" or nb_occ == 1):
        if (record.find(path, namespaces=ns) is not None and record.find(path, namespaces=ns).text is not None):
            val = record.find(path, namespaces=ns).text
            listeValues.append(val)
    else:
        for occ in record.xpath(path, namespaces=ns):
            if (occ.text is not None):
                listeValues.append(occ.text)
    listeValues = sep.join(listeValues)
    return listeValues

def form_saut_de_ligne(frame, couleur_fond):
    tk.Label(frame, text="\n", bg=couleur_fond).pack()

def form_generic_frames(master,title, couleur_fond, couleur_bordure,access_to_network):
#----------------------------------------------------
#|                    Frame                         |
#|            zone_alert_explications               |
#----------------------------------------------------
#|                    Frame                         |
#|             zone_access2programs                 |
#|                                                  |
#|              Frame           |       Frame       |
#|           zone_actions       |  zone_help_cancel |
#----------------------------------------------------
#|                    Frame                         |
#|                  zone_notes                      |
#----------------------------------------------------
    #master = tk.Tk()
    form = tk.Toplevel(master)
    form.config(padx=10,pady=10,bg=couleur_fond)
    form.title(title)
    try:
        form.iconbitmap(r'favicon.ico')
    except tk.TclError:
        favicone = "rien"

    zone_alert_explications = tk.Frame(form, bg=couleur_fond, pady=10)
    zone_alert_explications.pack()
    
    zone_access2programs = tk.Frame(form, bg=couleur_fond)
    zone_access2programs.pack()
    zone_actions = tk.Frame(zone_access2programs, bg=couleur_fond)
    zone_actions.pack(side="left")
    zone_ok_help_cancel = tk.Frame(zone_access2programs, bg=couleur_fond)
    zone_ok_help_cancel.pack(side="left")
    zone_notes = tk.Frame(form, bg=couleur_fond, pady=10)
    zone_notes.pack()

    if (access_to_network == False):
        tk.Label(zone_alert_explications, text=errors["no_internet"], 
                 bg=couleur_fond,  fg="red").pack()

    
    return [form,
            zone_alert_explications,
            zone_access2programs,
            zone_actions,
            zone_ok_help_cancel,
            zone_notes]

def main_form_frames(title, couleur_fond, couleur_bordure,access_to_network):
#----------------------------------------------------
#|                    Frame                         |
#|            zone_alert_explications               |
#----------------------------------------------------
#|                    Frame                         |
#|             zone_access2programs                 |
#|                                                  |
#|              Frame           |       Frame       |
#|           zone_actions       |  zone_help_cancel |
#----------------------------------------------------
#|                    Frame                         |
#|                  zone_notes                      |
#----------------------------------------------------
    master = tk.Tk()
    master.config(padx=10,pady=10,bg=couleur_fond)
    master.title(title)
    try:
        master.iconbitmap(r'favicon.ico')
    except tk.TclError:
        favicone = "rien"

    zone_alert_explications = tk.Frame(master, bg=couleur_fond, pady=10)
    zone_alert_explications.pack()
    
    zone_access2programs = tk.Frame(master, bg=couleur_fond)
    zone_access2programs.pack()
    zone_actions = tk.Frame(zone_access2programs, bg=couleur_fond)
    zone_actions.pack(side="left")
    zone_ok_help_cancel = tk.Frame(zone_access2programs, bg=couleur_fond)
    zone_ok_help_cancel.pack(side="left")
    zone_notes = tk.Frame(master, bg=couleur_fond, pady=10)
    zone_notes.pack()

    if (access_to_network == False):
        tk.Label(zone_alert_explications, text=errors["no_internet"], 
                 bg=couleur_fond,  fg="red").pack()

    
    return [master,
            zone_alert_explications,
            zone_access2programs,
            zone_actions,
            zone_ok_help_cancel,
            zone_notes]


def generic_input_controls(master,filename):
    check_file_name(master,filename)

def check_file_utf8(master, filename):
    try:
        open(filename, "r", encoding="utf-8")
    except FileNotFoundError:
        popup_errors(master,"Le fichier " + filename + " n'existe pas")
    except UnicodeDecodeError:
        popup_errors(master,errors["pb_input_utf8"])
        
       
def check_file_name(master,filename):
    try:
        open(filename,"r")
    except FileNotFoundError:
        popup_errors(master,"Le fichier " + filename + " n'existe pas")

def popup_errors(master,text,online_help_text="",online_help_link=""):
    couleur_fond = "white"
    couleur_bordure = "red"
    [master,
            zone_alert_explications,
            zone_access2programs,
            zone_actions,
            zone_ok_help_cancel,
            zone_notes] = form_generic_frames(master,"Alerte", couleur_fond, couleur_bordure,True)
    tk.Label(zone_access2programs, text=text, fg=couleur_bordure, 
             font="bold", bg=couleur_fond, padx=20, pady=20).pack()
    if (online_help_text != ""):
        help_button = tk.Button(zone_access2programs, bd=2, justify="left", font="Arial 10 italic",
                                bg="#ffffff",
                                padx=5,pady=5,
                                    text=online_help_text, command=lambda: click2openurl(online_help_link))
        help_button.pack()
    tk.Label(zone_access2programs, bg=couleur_fond, text="\n").pack()
    cancel = tk.Button(zone_access2programs, text="Fermer", command=lambda: annuler(master), padx=10, pady=1, width=15)
    cancel.pack()

#popup_filename = ""
    
def openfile(frame,liste,background_color="white"):
    liste = []
    liste.append(filedialog.askopenfilename(title='Sélectionner un fichier'))
    filename_print = liste[0].split("/")[-1].split("\\")[-1]
    tk.Label(frame,text=filename_print, bg=background_color).pack()

def download_button(frame,text,frame_selected,text_path,couleur_fond,file_entry_list,zone_message_en_cours=""):
    if (file_entry_list != []):
        text_path.delete(0.0,1000.3)
    filename = filedialog.askopenfilename(parent=frame,title="Sélectionner un fichier")
    if (file_entry_list == []):
        file_entry_list.append(filename)
    else:
        file_entry_list[0] = filename
    text_path.insert(0.0,filename)
    texte = """Après avoir lancé le traitement,
vous pourrez suivre sa progression sur le terminal (fenêtre écran noir).
    
Cette fenêtre se fermera toute seule à la fin du programme
et sa fermeture signifiera que le programme est arrivée à la fin du traitement"""
    if (zone_message_en_cours != ""):
        zone_message_en_cours.insert(0.0,texte)
    
def download_zone(frame, text_bouton,file_entry_list,couleur_fond,cadre_output_message_en_cours=""):
    frame_button = tk.Frame(frame)
    frame_button.pack()
    frame_selected = tk.Frame(frame)
    frame_selected.pack()
    display_selected = tk.Text(frame_selected, height=3, width=50, bg=couleur_fond, bd=0, font="Arial 9 bold")
    display_selected.pack()
    zone_message_en_cours = ""
    if (cadre_output_message_en_cours != "" and preferences["display_message_in_progress"]["value"]==1):
        zone_message_en_cours = tk.Text(cadre_output_message_en_cours, 
                                        height=5, width=70, fg="red",
                                        bg=couleur_fond, bd=0, font="Arial 9 bold")
        zone_message_en_cours.pack()
    #bouton_telecharger = download_button(frame,"Sélectionner un fichier","#ffffff")
    select_filename_button = tk.Button(frame_button,command=lambda:download_button(frame, 
                                                    text_bouton,
                                                    frame_selected,display_selected,
                                                    "#ffffff", file_entry_list,zone_message_en_cours),
                                text=text_bouton,
                                padx=10, pady=10)
    select_filename_button.pack()

def select_directory_button(frame,text,frame_selected,text_path,couleur_fond,directory_list):
    if (directory_list != []):
        text_path.delete(0.0,1000.3)
    filename = filedialog.askdirectory(parent=frame,title="Sélectionner un fichier")
    tk.folder_path.set(filename)
    if (directory_list == []):
        directory_list.append(filename)
    else:
        directory_list[0] = filename
    text_path.insert(0.0,filename)
    

def select_directory(frame, text_bouton,directory_list,couleur_fond):
    frame_button = tk.Frame(frame)
    frame_button.pack()
    frame_selected = tk.Frame(frame)
    frame_selected.pack()
    display_selected = tk.Text(frame_selected, height=3, width=50, bg=couleur_fond, bd=0, font="Arial 9 bold")
    display_selected.pack()
    #bouton_telecharger = download_button(frame,"Sélectionner un fichier","#ffffff")
    select_filename_button = tk.Button(frame_button,command=lambda:download_button(frame, 
                                                    text_bouton,
                                                    frame_selected,display_selected,
                                                    "#ffffff", directory_list),
                                text=text_bouton,
                                padx=10, pady=10)
    select_filename_button.pack()


def message_programme_en_cours(master, access_to_network=True, couleur_fond="#ffffff"):
    texte = """Le programme est en cours d'exécution.
Vous pouvez suivre sa progression sur le terminal (écran noir).
    
Cette fenêtre se fermera toute seule à la fin du programme
et sa fermeture signifiera que le programme est arrivée à la fin du traitement"""
    #zone_message.insert(0.0,texte)
    couleur_bouton = "#efefef"
    [form,
    zone_alert_explications,
    zone_access2programs,
    zone_actions,
    zone_ok_help_cancel,
    zone_notes] = form_generic_frames(master,"Traitement en cours",
                                      couleur_fond,couleur_bouton,
                                      access_to_network)
    a = tk.Label(zone_alert_explications, text=texte)
    a.pack()
    #form.mainloop()
    return form
    


def formulaire_main(access_to_network, last_version):
    couleur_fond = "white"
    couleur_bouton = "#e1e1e1"
    
    [master,
     zone_alert_explications,
     zone_access2programs,
     zone_actions,
     zone_ok_help_cancel,
     zone_notes] = main_form_frames("La Transition bibliographique en chantant nous ouvre...",
                                      couleur_fond,
                                      couleur_bouton,access_to_network)
    
    frame1 = tk.Frame(zone_actions, highlightthickness=2, highlightbackground=couleur_bouton, bg=couleur_fond, pady=20, padx=20)
    frame1.pack(side="left")
    
    frame2 = tk.Frame(zone_actions, highlightthickness=2, highlightbackground=couleur_bouton, bg=couleur_fond, pady=20, padx=20)
    frame2.pack(side="left")
    
    frame3 = tk.Frame(zone_actions, highlightthickness=2, highlightbackground=couleur_bouton, bg=couleur_fond, pady=20, padx=20)
    frame3.pack(side="left")
    
    frame_help_cancel = tk.Frame(zone_ok_help_cancel, bg=couleur_fond, pady=10, padx=10)
    frame_help_cancel.pack()
    
# =============================================================================
#     1er module : convertir un fichier MARC en tables
# =============================================================================
    marc2tableButton = tk.Button(frame1, text = "Convertir un fichier Marc\n en tableaux", 
                                 command=lambda: marc2tables.formulaire_marc2tables(master,access_to_network), 
                                 padx=10,pady=25, bg="#2D4991",fg="white")
    marc2tableButton.pack()
    
# =============================================================================
#   2e module : aligner ses données bibliographiques ou AUT  
# =============================================================================
    bib2arkButton = tk.Button(frame2, text = "Aligner ses données  BIB (tableaux)\n avec le catalogue BnF", 
                              command=lambda: bib2ark.formulaire_noticesbib2arkBnF(master,access_to_network,[0,False]), 
                              padx=10,pady=10, bg="#fefefe", font="Arial 9 bold")
    bib2arkButton.pack()
        
    aut2arkButton = tk.Button(frame2, text = "Aligner ses données AUT ", command=lambda: aut2ark.formulaire_noticesaut2arkBnF(master,access_to_network,[0,False]), 
                              padx=50,pady=1, bg="#fefefe", font="Arial 8 normal")
    aut2arkButton.pack()

# =============================================================================
#    3e module : exporter des notices à partir d'une liste d'ARK
# =============================================================================
    ark2recordsButton = tk.Button(frame3, text = "Exporter une liste d'ARK BnF\n en notices", 
                                  command=lambda: ark2records.formulaire_ark2records(master,access_to_network,[0,False]), 
                                  padx=10,pady=25, bg="#99182D", fg="white")
    ark2recordsButton.pack()


    
    tk.Label(zone_ok_help_cancel,text=" ", pady=5, bg=couleur_fond).pack()
    

    call4help = tk.Button(frame_help_cancel, text="Besoin d'aide ?", command=lambda: click2openurl("https://github.com/Transition-bibliographique/alignements-donnees-bnf"), pady=5, padx=5, width=12)
    call4help.pack()
    cancel = tk.Button(frame_help_cancel, text="Annuler", command=lambda: annuler(master), pady=5, padx=5, width=12)
    cancel.pack()



    tk.Label(zone_notes, text = "Version " + str(version) + " - " + lastupdate, bg=couleur_fond).pack()
    
    if (last_version[1] == True):
        download_update = tk.Button(zone_notes, text = "Télécharger la version " + str(last_version[0]), command=download_last_update)
        download_update.pack()

    
    tk.mainloop()
    

if __name__ == '__main__':
    access_to_network = check_access_to_network()
    last_version = [0,False]
    if(access_to_network is True):
        last_version = check_last_compilation(programID)
    formulaire_main(access_to_network, last_version)
