# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""
from django.template.defaulttags import register
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.template import loader
from django.http import HttpResponse
from django import template
from django.views.generic import TemplateView
from django.core.files.storage import FileSystemStorage
from django.views.decorators.csrf import csrf_protect
from django.core.cache import cache
from .forms import ParameterForm
import os
import sys
from app.models import File, Column, DetectedSmell, SmellType, Parameter
from django.contrib.auth.models import User

cwd = os.getcwd()
sys.path.append("/home/loryg/Documents/Gitlab/bachelor-thesis/data_smell_detection/")
from datasmelldetection.detectors.great_expectations.dataset import GreatExpectationsDatasetManager
from datasmelldetection.detectors.great_expectations.context import GreatExpectationsContextBuilder
from datasmelldetection.detectors.great_expectations.detector import DetectorBuilder
from datasmelldetection.detectors.great_expectations.detector import GreatExpectationsDetector
from datasmelldetection.detectors.great_expectations.profiler import DataSmellAwareProfiler
from datasmelldetection.detectors.great_expectations.detector import GreatExpectationsConfiguration
from datasmelldetection.core.detector import DetectionStatistics, DetectionResult
from datasmelldetection.core.datasmells import DataSmellType


dummy_user, c = User.objects.get_or_create(username="dummy_user")
# Different smells by it's category
believability_smells = {DataSmellType.DUMMY_VALUE_SMELL: {}, DataSmellType.DUPLICATED_VALUE_SMELL: {}, DataSmellType.EXTREME_VALUE_SMELL: {'mostly': 'double', 'threshold': 'integer'}, DataSmellType.MEANINGLESS_VALUE_SMELL: {}, DataSmellType.MISSPELLING_SMELL: {}, DataSmellType.SUSPECT_CLASS_VALUE_SMELL: {}, DataSmellType.SUSPECT_DATE_VALUE_SMELL: {}, DataSmellType.SUSPECT_DATE_TIME_INTERVAL_SMELL: {}, DataSmellType.SUSPECT_SIGN_SMELL: {'mostly': 'double', 'prercentile_threshold': 'double'}, DataSmellType.SUSPECT_DISTRIBUTION_SMELL: {}}
syntactic_understandability_smells = {DataSmellType.AMBIGUOUS_DATE_TIME_FORMAT_SMELL: {}, DataSmellType.AMBIGUOUS_VALUE_SMELL: {}, DataSmellType.CASING_SMELL: {}, DataSmellType.CONTRACTING_SMELL: {}, DataSmellType.EXTRANEOUS_VALUE_SMELL: {}, DataSmellType.INTERMINGLED_DATA_TYPE_SMELL: {}, DataSmellType.LONG_DATA_VALUE_SMELL: {}, DataSmellType.MISSING_VALUE_SMELL: {}, DataSmellType.SEPARATING_SMELL: {}, DataSmellType.SPACING_SMELL: {}, DataSmellType.SPECIAL_CHARACTER_SMELL: {}, DataSmellType.SYNONYM_SMELL: {}, DataSmellType.TAGGING_SMELL: {}}
encoding_understandability_smells = {DataSmellType.DATE_AS_DATE_TIME_SMELL: {}, DataSmellType.DATE_AS_STRING_SMELL: {}, DataSmellType.DATE_TIME_AS_STRING_SMELL: {}, DataSmellType.FLOATING_POINT_NUMBER_AS_STRING_SMELL: {'mostly': 'double'}, DataSmellType.INTEGER_AS_FLOATING_POINT_NUMBER_SMELL: {}, DataSmellType.INTEGER_AS_STRING_SMELL: {'mostly': 'double'}, DataSmellType.TIME_AS_STRING_SMELL: {}, DataSmellType.SUSPECT_CHARACTER_ENCODING_SMELL: {}}
consistency_smells = {DataSmellType.ABBREVIATION_INCONSISTENCY_SMELL: {}, DataSmellType.CASING_INCONSISTENCY_SMELL: {}, DataSmellType.CLASS_INCONSISTENCY_SMELL: {}, DataSmellType.DATE_TIME_FORMAT_INCONSISTENCY_SMELL: {}, DataSmellType.MISSING_VALUE_INCONSISTENCY_SMELL: {}, DataSmellType.SEPARATING_INCONSISTENCY_SMELL: {}, DataSmellType.SPACING_INCONSISTENCY_SMELL: {}, DataSmellType.SPECIAL_CHARACTER_INCONSISTENCY_SMELL: {}, DataSmellType.SYNTAX_INCONSISTENCY_SMELL: {}, DataSmellType.UNIT_INCONSISTENCY_SMELL: {}, DataSmellType.TRANSPOSITION_INCONSISTENCY_SMELL: {}}
all_smells = {'Believability Smells': believability_smells, 'Encoding Understandability Smells': encoding_understandability_smells, 'Syntactic Understandability Smells': syntactic_understandability_smells, 'Consistency Smells': consistency_smells}

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

def index(request):
    context = {}
    context['segment'] = 'index'

    html_template = loader.get_template( 'index.html' )
    return HttpResponse(html_template.render(context, request))

def pages(request):
    context = {}
    # All resource paths end in .html.
    # Pick out the html file name from the url. And load that template.
    try:
        
        load_template      = request.path.split('/')[-1]
        context['segment'] = load_template
        
        html_template = loader.get_template( load_template )
        return HttpResponse(html_template.render(context, request))
        
    except template.TemplateDoesNotExist:

        html_template = loader.get_template( 'page-404.html' )
        return HttpResponse(html_template.render(context, request))

    except:
        html_template = loader.get_template( 'page-403.html' )
        return HttpResponse(html_template.render(context, request))


def upload(request):
    global all_smells, believability_smells, syntactic_understandability_smells, encoding_understandability_smells, consistency_smells
    
    #https://jsfiddle.net/xg1kwv67/

    # Some presettings for data smell detection
    outer = os.path.join(os.getcwd(), "../")
    context_builder = GreatExpectationsContextBuilder(
        os.path.join(outer, "../great_expectations"),
        os.path.join(cwd, "core/media")
    )
    con = context_builder.build()
    manager = GreatExpectationsDatasetManager(context=con)
    context = {}

    if request.method == 'POST' and 'upload' in request.FILES:
        uploaded_file = request.FILES['upload']
        if '.csv' in uploaded_file.name:
            fs = FileSystemStorage()
            name = fs.save(uploaded_file.name, uploaded_file)
            context['url'] = fs.url(name)   
            context['size'] = fs.size(name) / 1000000
            file_name = context['url'].replace('/media/', '')

            # Save file to database
            if request.user.is_authenticated:
                file1 = File(file_name=file_name, user=request.user)
                file1.save()
            else:
                file1 = File(file_name=file_name, user=dummy_user)
                file1.save()
            
            dataset = manager.get_dataset(file_name)
            column_names = precheck_columns(dataset.get_column_names())
            detector = DetectorBuilder(context=con, dataset=dataset).build()
            supported_smells = detector.get_supported_data_smell_types()
            
            # Save supported smell to database
            for s in supported_smells:
                smell = SmellType(smell_type=s.value)
                smell.save()
                smell.belonging_file.add(file1)
                
                # Save parameters for smells
                parameters = believability_smells.get(s) or syntactic_understandability_smells.get(s) or encoding_understandability_smells.get(s) or consistency_smells.get(s)
                if parameters is not None:
                    for p,v in parameters.items():
                        par = Parameter(name=p, value=0.0, data_type=v, belonging_smell=smell, belonging_file=file1)
                        par.save()
            columns = precheck_columns(dataset.get_column_names())
            for c in columns:
                Column.objects.create(column_name=c, belonging_file=file1)
        else:
            context['message'] = 'Upload a .csv file.'
    else:
        context['message'] = 'no file selected'
    return render(request, 'index.html', context)


def smells(request):
    context = {}
    global all_smells
    
    all_smells_list = list(believability_smells.keys()) + list(syntactic_understandability_smells.keys()) + list(encoding_understandability_smells.keys()) + list(consistency_smells.keys())

    if request.user.is_authenticated:
        current_user_id = request.user.id
    else:
        current_user_id = dummy_user.id
    
    # Get file and available smells
    file1 = File.objects.filter(user_id=current_user_id).latest("uploaded_time")
    smells = SmellType.objects.all().filter(belonging_file=file1)#.get().smell_type
    new = []
    for l in list(smells):
        new.append(l.smell_type)

    available_smells = {i: {a:b for (a,b) in j.items() if a.value in new} for i,j in all_smells.items()}
    
    # Get column names by id and by name
    column_names_by_id = list(Column.objects.all().filter(belonging_file=file1))
    column_names = [c.column_name for c in column_names_by_id]
    
    # Smells and column names for customization
    context['smells'] = available_smells
    context['column_names'] = column_names
    

    if request.method == 'POST':
      # Selected smells and column names
      #test_form = CustomizationForm(request.POST, prefix='test_form')
      smells_list = request.POST.getlist('smells')  
      columns = request.POST.getlist('columns')
      forms = dict(available_smells)

      for k,values in available_smells.items():
          temp = dict(values)
          for v in values:
            smell_db = SmellType.objects.get(smell_type=v.value)
            parameter_list = list(Parameter.objects.all().filter(belonging_smell=smell_db))
            form_dict = {}
            for p in parameter_list:
                prefix_name = str(v)+str(p)
                form_dict[p.name] = ParameterForm(request.POST, prefix=prefix_name, instance=p)

                if form_dict[p.name].is_valid():
                    form_dict[p.name].save()

            temp[v] = dict(form_dict)
          forms[k] = dict(temp)

      if smells_list and columns:
        context['list_smells'] = [s.split('.')[1].replace("_", " ") for s in smells_list]
        context['list_columns'] = columns
    
        # Delete columns which should not be detected according to user's customization
        columns_to_delete = []
        for c in column_names_by_id:
            if c.column_name not in columns:
                columns_to_delete.append(c.id)
        for c in columns_to_delete:
            Column.objects.get(id=c).delete()

        smells_to_delete = []
        for s in list(smells):
            if 'DataSmellType.'+s.smell_type.replace(" ", "_").upper() not in smells_list:
                s.belonging_file.remove(file1)
      else:
        context['message'] = 'Select smells AND columns!'    
    else:
        forms = dict(available_smells)
        for k,values in available_smells.items():
          temp = dict(values)
          for v in values:
            smell_db = SmellType.objects.get(smell_type=v.value)
            parameter_list = list(Parameter.objects.all().filter(belonging_smell=smell_db))
            form_dict = {}
            for p in parameter_list:
                prefix_name = str(v)+str(p)
                form_dict[p.name] = ParameterForm(prefix=prefix_name, instance=p)
            temp[v] = dict(form_dict)
          forms[k] = dict(temp)
    context['forms'] = forms

    return render(request, 'customize.html', context)

def result(request):
    # Some presettings for data smell detection
    context = {}
    outer = os.path.join(os.getcwd(), "../")
    context_builder = GreatExpectationsContextBuilder(
        os.path.join(outer, "../great_expectations"),
        os.path.join(cwd, "core/media")
    )
    con = context_builder.build()
    manager = GreatExpectationsDatasetManager(context=con)
    
    if request.user.is_authenticated:
        current_user_id = request.user.id
    else:
        current_user_id = dummy_user.id

    try:
        # Get file for detection
        file1 = File.objects.filter(user_id=current_user_id).latest("uploaded_time")
        dataset = manager.get_dataset(file1.file_name)
        column_names = [c.column_name for c in list(Column.objects.all().filter(belonging_file=file1))]
        smells = list(SmellType.objects.all().filter(belonging_file=file1))
        ds_config = {}
        for s in smells:
            pars = list(Parameter.objects.all().filter(belonging_smell=s))
            par_dict = {}
            for p in pars:
                par_dict[p.name] = p.value

            temp = DataSmellType(s.smell_type)
            ds_config[temp] = dict(par_dict)

        conf = GreatExpectationsConfiguration(
            column_names=column_names,
            data_smell_configuration=ds_config
        )
        detector = DetectorBuilder(context=con, dataset=dataset).set_configuration(conf).build() 

        # Detect smells and sort result
        detected_smells = detector.detect()
        sorted_results = sort_results(detected_smells, column_names)
        print(sorted_results)
        # Save detected smell to database
        for key, value in sorted_results.items():
            column1 = Column.objects.get(column_name=key, belonging_file=file1)
            for v in value:
                data_smell_t = SmellType.objects.get(smell_type=v.data_smell_type.value)
                DetectedSmell.objects.create(data_smell_type=data_smell_t, total_element_count=v.statistics.total_element_count, faulty_element_count=v.statistics.faulty_element_count, faulty_list=v.faulty_elements, belonging_column=column1)

        context['column_names'] = column_names
        context['results'] = sorted_results
        context['file'] = file1.file_name
        if request.method == 'POST':
            File.objects.get(file_name=file1.file_name).delete()
            context['delete_message'] = 'Result deleted and not viewable in Saved Results.'

    except:
       context['no_file'] = 'No detection result for this user available.'

    return render(request, 'results.html', context)

@login_required
def saved(request):

    if request.method == 'POST':
        file_name = request.POST.get('del')
        try:
            File.objects.get(file_name=file_name).delete()
        except:
            pass
    # Some presettings for data smell detection
    context = {}
    outer = os.path.join(os.getcwd(), "../")
    context_builder = GreatExpectationsContextBuilder(
        os.path.join(outer, "../great_expectations"),
        os.path.join(cwd, "core/media")
    )
    con = context_builder.build()
    manager = GreatExpectationsDatasetManager(context=con)
    
    if request.user.is_authenticated:
        current_user_id = request.user.id
    else:
        current_user_id = dummy_user.id

    files = File.objects.all().filter(user_id=current_user_id).order_by('-uploaded_time')
    
    parameter_dict = {}
    results = {}
    for f in files:
        all_columns = list(Column.objects.all().filter(belonging_file=f))
        all_smells_for_file = [] #list(DetectedSmell.objects.all().filter(belonging_file=f))
        for c in all_columns:
            all_smells_for_file.extend(list(DetectedSmell.objects.all().filter(belonging_column=c)))
        sorted_results = {}
        
        # Delete files which do not have any detected smells
        if not all_smells_for_file:
            File.objects.get(file_name=f.file_name).delete()
            continue

        smell_dict = {}
            
        for c in all_columns:
            sorted_results[c] = []
            for s in all_smells_for_file:
                if s.belonging_column.column_name == c.column_name:
                    sorted_results[c].append(s)
                    s_type = SmellType.objects.get(smell_type=s.data_smell_type.smell_type)
                    smell_dict[s.data_smell_type.smell_type] = list(Parameter.objects.all().filter(belonging_smell=s_type, belonging_file=f))
                    parameter_dict[f.file_name] = dict(smell_dict)

        context['parameter_dict'] = parameter_dict
        results[f.file_name] = sorted_results
    context['results'] = results

    return render(request, 'saved.html', context)

def sort_results(results, columns):
    sorted_results = {}
    for c in columns:
        sorted_results[c] = []
        for s in results:
            if s.column_name == c:
                sorted_results[c].append(s)
    return sorted_results

def precheck_columns(columns):
    if "Unnamed: 0" in columns:
        columns.remove("Unnamed: 0")
    return sorted(columns)
