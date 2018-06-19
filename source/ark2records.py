# -*- coding: utf-8 -*-
"""
Created on Mon Oct 30 17:55:32 2017

@author: Etienne Cavalié

A partir d'un fichier contenant une liste d'ARK de notices biblio, récupérer les
notices complètes (en XML)
+ option pour récupérer les notices d'autorité
"""

import csv
import os
import re
import tkinter as tk
import urllib.parse
from urllib import error, request

import pymarc as mc
from lxml import etree

from . import funcs
from . import main
from . import noticesbib2arkBnF as bib2ark


version = 0.02
programID = "ark2records"
lastupdate = "12/11/2017"
last_version = [version, False]

# Permet d'écrire dans une liste accessible au niveau général depuis le
# formulaire, et d'y accéder ensuite
entry_file_list = []

listeARK_BIB = []
listeNNA_AUT = []
errors_list = []

dict_format_records = {
    1: "unimarcxchange",
    2: "unimarcxchange-anl",
    3: "intermarcxchange",
    4: "intermarcxchange-anl"}
listefieldsLiensAUT = {
    "unimarc": ["100", "700", "702", "703", "709", "710", "712", "713", "719", "731"],
    "intermarc": ["100", "700", "702", "703", "709", "710", "712", "713", "719", "731"]}
listefieldsLiensSUB = {
    "unimarc": ["600", "603", "606", "607", "609", "610", "616", "617"],
    "intermarc": ["600", "603", "606", "607", "609", "610", "616", "617"]}
listefieldsLiensWORK = {
    "unimarc": ["500"],
    "intermarc": ["141", "144", "145"]}


def ark2url(ark, parametres):
    query = parametres["type_records"] + '.persistentid any "' + ark + '"'
    if (parametres["type_records"] == "aut"):
        query += ' and aut.status any "sparse validated"'
    query = urllib.parse.quote(query)
    url = "http://catalogue.bnf.fr/api/SRU?version=1.2&operation=searchRetrieve&query=" + query + \
        "&recordSchema=" + parametres["format_BIB"] + \
        "&maximumRecords=20&startRecord=1&origin=bibliostratus"
    if (ark[0:3].lower() == "ppn" and parametres["type_records"] == "bib"):
        url = "https://www.sudoc.fr/" + ark[3:] + ".xml"
    elif (ark[0:3].lower() == "ppn" and parametres["type_records"] == "aut"):
        url = "https://www.idref.fr/" + ark[3:] + ".xml"
    return url


def nn2url(nn, type_record, parametres, source="bnf"):
    if (source == "bnf"):
        query = type_record + '.recordid any "' + nn + '"'
        if (type_record == "aut"):
            query += ' and aut.status any "sparse validated"'
        query = urllib.parse.quote(query)
        url = "http://catalogue.bnf.fr/api/SRU?version=1.2&operation=searchRetrieve&query=" + \
            query + "&recordSchema=" + \
            parametres["format_BIB"] + "&maximumRecords=20&startRecord=1"
    elif (source == "sudoc"):
        url = "http://www.sudoc.fr/" + nn + ".xml"
    elif (source == "idref"):
        url = "http://www.idref.fr/" + nn + ".xml"
    return url


def ark2record(ark, type_record, format_BIB, renvoyerNotice=False):
    url = ark2url(ark, type_record, format_BIB)
    test = True
    try:
        page = etree.parse(request.urlopen(url))
    except error.URLerror:
        test = False
        print("Pb d'accès à la notice " + ark)
    if test:
        record = page.xpath(".//srw:recordData/mxc:record",
                            namespaces=main.ns)[0]
    if renvoyerNotice:
        return record


def XMLrecord2string(record):
    record_str = str(etree.tostring(record))
    record_str = record_str.replace("b'", "").replace("      '", "\n").replace(
        "\\n", "\n").replace("\\t", "\t").replace("\\r", "\n")
    return (record_str)


def extract_nna_from_bib_record(record, field, source):
    """Extraction de la liste des identifiants d'auteurs à partir
    d'une zone de notice bib"""
    liste_nna = []
    if (source == "bnf"):
        path = '//mxc:datafield[@tag="' + field + '"]/mxc:subfield[@code="3"]'
    elif(source == "sudoc" or source == "idref"):
        path = '//datafield[@tag="' + field + '"]/subfield[@code="3"]'
    for datafield in record.xpath(path, namespaces=main.ns):
        nna = datafield.text
        if (nna not in listeNNA_AUT):
            listeNNA_AUT.append(nna)
            liste_nna.append(nna)
    return liste_nna


def bib2aut(XMLrecord, ark, parametres):
    """Si une des option "Récupérer les notices d'autorité liées" est cochée
    récupération des identifiants de ces AUT pour les récupérer"""
    source = "bnf"
    if ("ppn" in ark.lower()):
        source = "sudoc"
    liste_nna = []
    listefields = []
    format_marc = parametres["format_BIB"].split("x")[0]
    if (parametres["AUTlieesAUT"] == 1):
        listefields.extend(listefieldsLiensAUT[format_marc])
    if (parametres["AUTlieesSUB"] == 1):
        listefields.extend(listefieldsLiensSUB[format_marc])
    if (parametres["AUTlieesWORK"] == 1):
        listefields.extend(listefieldsLiensWORK[format_marc])
    for field in listefields:
        liste_nna.extend(extract_nna_from_bib_record(XMLrecord, field, source))
    for nna in liste_nna:
        if (source == "sudoc"):
            source = "idref"
        url = nn2url(nna, "aut", parametres, source)
        (test, record) = funcs.testURLetreeParse(url)
        if (test and source == "bnf" and record.find(
                "//srw:recordData/mxc:record", namespaces=main.ns) is not None):
            XMLrec = record.xpath(
                ".//srw:recordData/mxc:record", namespaces=main.ns
            )[0]
            record2file(parametres["aut_file"], XMLrec,
                        parametres["format_file"])
        elif (test and source == "idref" and record.find("//record") is not None):
            XMLrec = record.xpath(".//record")[0]
            record2file(parametres["aut_file"], XMLrec,
                        parametres["format_file"])


def file_create(record_type, parametres):
    file = object
    id_filename = "-".join([parametres["outputID"], record_type])
    if (parametres["format_file"] == 2):
        filename = id_filename + ".xml"
        file = open(filename, "w", encoding="utf-8")
        file.write("<?xml version='1.0'?>\n")
        file.write("<mxc:collection ")
        for key in main.ns:
            file.write(' xmlns:' + key + '="' + main.ns[key] + '"')
        file.write(">\n")
    else:
        filename = id_filename + ".iso2709"
        file = mc.MARCWriter(open(filename, "wb"))
    return file


def file_fin(file, format_file):
    if (format_file == 2):
        file.write("</mxc:collection>")
    file.close()


def XMLrec2isorecord(XMLrec):
    XMLrec = XMLrec.replace("<mxc:", "<").replace("</mxc:", "</")
    XMLrec = "<collection>" + XMLrec + "</collection>"
    XMLrec = re.sub(r"<record[^>]+>", r"<record>", XMLrec)
    filename_temp = "temp.xml"
    file_temp = open(filename_temp, "w", encoding="utf-8")
    file_temp.write(XMLrec)
    return filename_temp


def record2file(file, XMLrec, format_file):
    # Si sortie en iso2709
    if (format_file == 1):
        XMLrec_str = XMLrecord2string(XMLrec)
        filename_temp = XMLrec2isorecord(XMLrec_str)
        collection = mc.marcxml.parse_xml_to_array(filename_temp, strict=False)
        for record in collection:
            record.force_utf8 = True
            try:
                file.write(record)
            except UnicodeEncodeError as err:
                errors_list.append([XMLrec_str, str(err)])
    # si sortie en XML
    if (format_file == 2):
        record = XMLrecord2string(XMLrec)
        file.write(record)


def page2nbresults(page, ark):
    if (ark[0:3].lower() == "ppn"):
        nbresults = 0
        if (page.find("//leader") is not None):
            nbresults = "1"
    else:
        nbresults = page.find("//srw:numberOfRecords", namespaces=main.ns).text
    return nbresults


def extract1record(row, j, form, headers, parametres):
    ark = row[0]
    ark = ark.replace("http://www.sudoc.fr/",
                      "ppn").replace("https://www.sudoc.fr/", "ppn")
    if ("ark:/12148" in ark):
        ark = ark[ark.find("ark:/12148"):]
    if (len(ark) > 1 and ark not in listeARK_BIB):
        print(str(j) + ". " + ark)
        listeARK_BIB.append(ark)
        (test, page) = funcs.testURLetreeParse(ark2url(ark, parametres))
        if(test):
            nbResults = page2nbresults(page, ark)
            if (nbResults == "1" and "ark" in ark):
                for XMLrec in page.xpath(
                        "//srw:record/srw:recordData/mxc:record",
                        namespaces=main.ns):
                    record2file(
                        parametres["bib_file"], XMLrec,
                        parametres["format_file"]
                    )
                    if (parametres["AUTliees"] > 0):
                        bib2aut(XMLrec, ark, parametres)
            elif (nbResults == "1" and "ppn" in ark.lower()):
                for XMLrec in page.xpath("//record"):
                    record2file(parametres["bib_file"],
                                XMLrec, parametres["format_file"])
                    if (parametres["AUTliees"] > 0):
                        bib2aut(XMLrec, ark, parametres)


def callback(master, form, filename, type_records_form, headers, AUTlieesAUT,
             AUTlieesSUB, AUTlieesWORK, outputID, format_records=1, format_file=1):
    AUTliees = AUTlieesAUT + AUTlieesSUB + AUTlieesWORK
    format_BIB = dict_format_records[format_records]
    type_records = "bib"
    if (type_records_form == 2):
        type_records = "aut"
    parametres = {
        "type_records": type_records,
        "type_records_form": type_records_form,
        "AUTliees": AUTliees,
        "AUTlieesAUT": AUTlieesAUT,
        "AUTlieesSUB": AUTlieesSUB,
        "AUTlieesWORK": AUTlieesWORK,
        "outputID": outputID,
        "format_records": format_records,
        "format_file": format_file,
        "format_BIB": format_BIB
    }
    main.generic_input_controls(master, filename)

    bib_file = file_create(type_records, parametres)
    parametres["bib_file"] = bib_file
    if (parametres["AUTliees"] > 0):
        aut_file = file_create("aut", parametres)
        parametres["aut_file"] = aut_file
    with open(filename, newline='\n', encoding="utf-8") as csvfile:
        entry_file = csv.reader(csvfile, delimiter='\t')
        if headers:
            next(entry_file, None)
        j = 0
        for row in entry_file:
            extract1record(row, j, form, headers, parametres)
            j = j + 1

        file_fin(bib_file, format_file)
        if (AUTliees == 1):
            file_fin(aut_file, format_file)
    fin_traitements(form, outputID)


def errors_file(outputID):
    errors_file = open(outputID + "-errors.txt", "w", encoding="utf-8")
    for el in errors_list:
        errors_file.write(el[1] + "\n" + el[0] + "\n\n")


def fin_traitements(window, outputID):
    if (errors_list != []):
        errors_file(outputID)
    if (os.path.isfile("temp.xml") is True):
        os.remove("temp.xml")
    print("Programme d'extraction de notices terminé")
    window.destroy()


# ==============================================================================
# Création de la boîte de dialogue
# ==============================================================================

def formulaire_ark2records(
        master, access_to_network=True, last_version=[version, False]):
    couleur_fond = "white"
    couleur_bouton = "#99182D"

    [form,
     zone_alert_explications,
     zone_access2programs,
     zone_actions,
     zone_ok_help_cancel,
     zone_notes] = main.form_generic_frames(
         master,
         "Bibliostratus : Récupérer les notices complètes de la BnF à partir d'une liste d'ARK",
         couleur_fond, couleur_bouton,
         access_to_network)

    zone_ok_help_cancel.config(padx=10)

    frame_input = tk.Frame(zone_actions,
                           bg=couleur_fond, padx=10, pady=10,
                           highlightthickness=2, highlightbackground=couleur_bouton)
    frame_input.pack(side="left", anchor="w", padx=10, pady=10)
    frame_input_file = tk.Frame(frame_input, bg=couleur_fond)
    frame_input_file.pack()
    frame_input_aut = tk.Frame(frame_input, bg=couleur_fond)
    frame_input_aut.pack()

    frame_output = tk.Frame(zone_actions,
                            bg=couleur_fond, padx=10, pady=10,
                            highlightthickness=2, highlightbackground=couleur_bouton)
    frame_output.pack(side="left", anchor="w")

    frame_output_options = tk.Frame(
        frame_output, bg=couleur_fond, padx=10, pady=10)
    frame_output_options.pack(anchor="w")
    frame_output_file = tk.Frame(
        frame_output, bg=couleur_fond, padx=10, pady=10)
    frame_output_file.pack(anchor="w")
    frame_output_options_marc = tk.Frame(frame_output_options, bg=couleur_fond)
    frame_output_options_marc.pack(side="left", anchor="nw")
    frame_output_options_inter = tk.Frame(
        frame_output_options, bg=couleur_fond)
    frame_output_options_inter.pack(side="left")
    frame_output_options_format = tk.Frame(
        frame_output_options, bg=couleur_fond)
    frame_output_options_format.pack(side="left", anchor="nw")

    zone_notes_message_en_cours = tk.Frame(
        zone_notes, padx=20, bg=couleur_fond)
    zone_notes_message_en_cours.pack()

    # tk.Label(frame_input_file, text="Fichier contenant les ARK\n (1 par ligne) \n\n",
    #         bg=couleur_fond, justify="left").pack(side="left", anchor="w")
    """entry_filename = tk.Entry(frame_input_file, width=20, bd=2, bg=couleur_fond)
    entry_filename.pack(side="left")
    entry_filename.focus_set()"""
    main.download_zone(
        frame_input_file,
        "Sélectionner un fichier contenant\nune liste d'ARK (un ARK par ligne)",
        entry_file_list, couleur_fond, zone_notes_message_en_cours
    )

    tk.Label(frame_input_aut, text="\n", bg=couleur_fond).pack()

    # ARK de BIB ou d'AUT ?
    type_records = tk.IntVar()
    bib2ark.radioButton_lienExample(
        frame_input_aut, type_records, 1, couleur_fond, "ARK de notices BIB",
        "",
        "https://raw.githubusercontent.com/Transition-bibliographique/alignements-donnees-bnf/master/examples/listeARKbib.tsv"  # noqa
    )
    bib2ark.radioButton_lienExample(
        frame_input_aut, type_records, 2, couleur_fond, "ARK de notices AUT",
        "",
        "https://raw.githubusercontent.com/Transition-bibliographique/alignements-donnees-bnf/master/examples/listeARKaut.tsv"  # noqa
    )
    type_records.set(1)

    tk.Label(frame_input_aut, text="-------------------",
             bg=couleur_fond).pack()

    # Fichier avec en-têtes ?
    headers = tk.IntVar()
    tk.Checkbutton(frame_input_aut, text="Mon fichier a des en-têtes de colonne",
                   variable=headers,
                   bg=couleur_fond, justify="left").pack(anchor="w")

    headers.set(1)

    # notices d'autorité liées
    tk.Label(frame_input_aut, text="Récupérer aussi les notices d'autorité liées",
             bg=couleur_fond, justify="left", font="Arial 9 bold").pack(anchor="w")
    AUTlieesAUT = tk.IntVar()
    tk.Checkbutton(frame_input_aut, text="auteurs",
                   variable=AUTlieesAUT,
                   bg=couleur_fond, justify="left").pack(anchor="w", side="left")
    # tk.Label(frame_input_aut, text="\n", bg=couleur_fond).pack()
    AUTlieesSUB = tk.IntVar()
    tk.Checkbutton(frame_input_aut, text="sujets",
                   variable=AUTlieesSUB,
                   bg=couleur_fond, justify="left").pack(anchor="w", side="left")
    AUTlieesWORK = tk.IntVar()
    tk.Checkbutton(frame_input_aut, text="oeuvres",
                   variable=AUTlieesWORK,
                   bg=couleur_fond, justify="left").pack(anchor="w", side="left")

    # Choix du format
    tk.Label(frame_output_options_marc,
             text="Notices à récupérer en :").pack(anchor="nw")
    format_records_choice = tk.IntVar()
    tk.Radiobutton(frame_output_options_marc, text="Unimarc",
                   variable=format_records_choice, value=1, bg=couleur_fond).pack(anchor="nw")
    tk.Radiobutton(frame_output_options_marc, text="Intermarc", justify="left",
                   variable=format_records_choice, value=3, bg=couleur_fond).pack(anchor="nw")
    tk.Radiobutton(
        frame_output_options_marc,
        text="Unimarc avec notices analytiques",
        justify="left",
        variable=format_records_choice,
        value=2,
        bg=couleur_fond
    ).pack(anchor="nw")
    tk.Radiobutton(
        frame_output_options_marc,
        text="Intermarc avec notices analytiques",
        justify="left",
        variable=format_records_choice,
        value=4,
        bg=couleur_fond
    ).pack(anchor="nw")
    format_records_choice.set(1)

    tk.Label(frame_output_options_inter, text="\n",
             bg=couleur_fond).pack(side="left")

    # tk.Label(
    #     frame_output_options,
    #     text="\n\n",
    #     justify="left",
    #     variable=format_records_choice,
    #     value=4,
    #     bg=couleur_fond
    # ).pack()

    tk.Label(frame_output_file, text="Préfixe fichier(s) en sortie",
             bg=couleur_fond).pack(side="left", anchor="w")
    outputID = tk.Entry(frame_output_file, bg=couleur_fond)
    outputID.pack(side="left", anchor="w")
    tk.Label(frame_output_file, text="\n\n\n\n\n\n\n",
             bg=couleur_fond).pack(side="left")

    tk.Label(frame_output_options_format,
             text="Format du fichier :").pack(anchor="nw")
    format_file = tk.IntVar()
    tk.Radiobutton(frame_output_options_format, bg=couleur_fond,
                   text="iso2709", variable=format_file, value=1, justify="left").pack(anchor="nw")
    tk.Radiobutton(frame_output_options_format, bg=couleur_fond,
                   text="Marc XML", variable=format_file, value=2, justify="left").pack(anchor="nw")
    format_file.set(1)

    # file_format.focus_set()
    b = tk.Button(
        zone_ok_help_cancel,
        text="OK",
        command=lambda: callback(
            master,
            form,
            entry_file_list[0],
            type_records.get(),
            headers.get(),
            AUTlieesAUT.get(),
            AUTlieesSUB.get(),
            AUTlieesWORK.get(),
            outputID.get(),
            format_records_choice.get(),
            format_file.get(),
        ),
        width=15,
        borderwidth=1,
        pady=20,
        fg="white",
        bg=couleur_bouton,
    )
    b.pack()

    main.form_saut_de_ligne(zone_ok_help_cancel, couleur_fond)
    call4help = tk.Button(zone_ok_help_cancel,
                          text=main.texte_bouton_help,
                          command=lambda: main.click2url(main.url_online_help),
                          pady=5, padx=5, width=12)
    call4help.pack()
    tk.Label(zone_ok_help_cancel, text="\n",
             bg=couleur_fond, font="Arial 1 normal").pack()

    forum_button = tk.Button(zone_ok_help_cancel,
                             text=main.texte_bouton_forum,
                             command=lambda: main.click2url(
                                 main.url_forum_aide),
                             pady=5, padx=5, width=12)
    forum_button.pack()

    tk.Label(zone_ok_help_cancel, text="\n",
             bg=couleur_fond, font="Arial 4 normal").pack()
    cancel = tk.Button(zone_ok_help_cancel, text="Annuler", bg=couleur_fond,
                       command=lambda: main.annuler(form), pady=10, padx=5, width=12)
    cancel.pack()

    tk.Label(zone_notes, text="Bibliostratus - Version " +
             str(main.version) + " - " + main.lastupdate, bg=couleur_fond).pack()

    # if (main.last_version[1] == True):
    #     download_update = tk.Button(
    #         zone_notes,
    #         text="Télécharger la version " + str(main.last_version[0]),
    #         command=download_last_update
    #     )
    #     download_update.pack()

    tk.mainloop()


if __name__ == '__main__':
    access_to_network = main.check_access_to_network()
    # if(access_to_network is True):
    #    last_version = main.check_last_compilation(programID)
    main.formulaire_main(access_to_network, last_version)
    # formulaire_ark2records(access_to_network,[version, False])
