"""
This script contains functions for main display
rlsn 2024
"""
import pyperclip
from nicegui import ui
import asyncio
from pygestor import load_meta, DATA_DIR, download, remove, stream_dataset, process_samples
from pygestor.utils import read_schema, AttrDict, Mutable
from pygestor.webui.infoview import *
from pygestor.webui.webui_utils import stream_load_code_snipet, full_load_code_snipet
from pygestor.webui import webui_config
from pygestor.webui.styles import *

_title_style = 'color: #646464; font-size: 180%; font-weight: bold; margin-left:50px;'
_view_height = '750px'
_info_list_classes = "w-full h-[1000px] px-0 py-0"
_snipet_style = 'width: 800px; height: 600px; max-width: none; max-height: none'
_button_column_classes = 'w-3/4 items-center px-0 py-0 gap-2'

def dataset_table(metadata):
    columns = [
        {'name': 'name', 'label': 'Dataset', 'field': 'name', 'required': True, 'align': 'left', 'sortable': True},
        {'name': 'modality', 'label': 'Modality', 'field': 'modality', 'sortable': True},
        {'name': 'src', 'label': 'Source', 'field': 'src', 'align': 'left'},
        {'name': 'desc', 'label': 'Description', 'field': 'desc', 'align': 'left', 'style': 'text-wrap: wrap;'},
    ]
    rows = []
    for ds in metadata["datasets"]:
        rows.append({
            'name': ds, 
            'modality': ",".join(metadata["datasets"][ds]["modality"]),
            'desc': metadata["datasets"][ds]["description"],
            'src': metadata["datasets"][ds]["source"],
        })

    return columns, rows

def subset_table(metadata):
    columns = [
        {'name': 'name', 'label': 'Subset', 'field': 'name', 'required': True, 'align': 'left', 'sortable': True},
        {'name': 'size', 'label': 'Size (MB)', 'field': 'size', 'sortable': True},
        {'name': 'downloaded', 'label': 'Downloaded', 'field': 'downloaded', 'sortable': True},
        {'name': 'partitions', 'label': 'Partitions', 'field': 'partitions', 'sortable': True},
        {'name': 'desc', 'label': 'Description', 'field': 'desc', 'align': 'left', 'style': 'text-wrap: wrap;'},
    ]
    rows = []
    for subs in metadata["subsets"]:
        info = metadata["subsets"][subs]
        downloaded = compute_subset_download(info)
        parts = info['partitions']
        rows.append({
            'name': subs, 
            'size': round(compute_subset_size(info)/1e6,3),
            'downloaded': downloaded,
            'partitions': len(parts),
            'desc': info["description"],
        })

    return columns, rows


def partition_table(metadata):
    columns = [
        {'name': 'name', 'label': 'Partition', 'field': 'name', 'required': True, 'align': 'left', 'sortable': True},
        {'name': 'size', 'label': 'Size (MB)', 'field': 'size', 'sortable': True},
        {'name': 'downloaded', 'label': 'Downloaded', 'field': 'downloaded', 'sortable': True},
    ]
    rows = []
    for part in metadata["partitions"]:
        info = metadata["partitions"][part]
        rows.append({
            'name': part, 
            'size': round(info["size"]/1e6,3),
            'downloaded': 'Yes' if info["downloaded"] else 'No',
        })

    return columns, rows

def show_partition_info(views, metadata, path, selected_parts=[]):
    name, subs, part = path
    infoview = views["infoview"]
    infoview.clear()
    info = metadata["datasets"][name]["subsets"][subs]["partitions"][part]

    async def on_download():
        n = ui.notification(timeout=None)
        n.message = 'Downloading : See progress on the webui server'
        n.spinner = True
        await asyncio.sleep(0.1)
        async def coro():
            await asyncio.to_thread(download, name, subset=subs, 
                                    partitions=selected_parts if len(selected_parts)>0 else [part], force_redownload=False)

        task = asyncio.create_task(coro())
        await task

        n.message = 'Done!'
        n.spinner = False
        metadata["datasets"]=load_meta()["datasets"]
        show_partitions(views, metadata, path[:2])
        await asyncio.sleep(2)
        n.dismiss()

    async def on_remove():
        n = ui.notification(timeout=None)
        n.message = 'Removing data ...'
        n.spinner = True
        await asyncio.sleep(0.1)
        async def coro():
            await asyncio.to_thread(remove, name, subset=subs, 
                                    partitions=selected_parts if len(selected_parts)>0 else [part], force_remove=True)
        task = asyncio.create_task(coro())
        await task

        n.message = 'Done!'
        n.spinner = False
        metadata["datasets"]=load_meta()["datasets"]
        show_partitions(views, metadata, path[:2])
        await asyncio.sleep(2)
        n.dismiss()

    with infoview:
        with ui.dialog() as dialog, ui.card().classes('items-center'):
            ui.label('You are about to remove the downloaded data.')
            ui.markdown('**Are you sure?**')
            with ui.grid(columns=2).classes('w-full items-center'):
                ui.button('Yes', icon="delete", on_click=on_remove).classes('w-full').props(f'color=red')
                ui.button('No', on_click=dialog.close).classes('w-full')

        with ui.dialog() as snipet, ui.card().classes('items-center').style(_snipet_style):
            tab_names = ['Stream', 'Full']
            codemirrors = []
            with ui.tabs().classes('w-full') as tabs:
                codemirrors.append(ui.tab(tab_names[0]).classes('w-full'))
                codemirrors.append(ui.tab(tab_names[1]).classes('w-full'))
            with ui.tab_panels(tabs, value=tab_names[0]).classes('w-full'):
                with ui.tab_panel(tab_names[0]).classes('w-full'):
                    codemirrors[0] = ui.codemirror(
                        stream_load_code_snipet(name,subs, 
                                                selected_parts if len(selected_parts)>0 else [part]),
                                              line_wrapping=True, language='Python').classes('h-full')
                with ui.tab_panel(tab_names[1]).classes('w-full'):
                    codemirrors[1] = ui.codemirror(
                        full_load_code_snipet(name,subs, 
                                              selected_parts if len(selected_parts)>0 else [part]), 
                                              line_wrapping=True, language='Python').classes('h-full')
            ui.button('Copy', 
                    on_click=lambda: (
                        pyperclip.copy(codemirrors[tab_names.index(tabs.value)].value),
                        ui.notify("Copied to clipboard"),
                        snipet.close()
                    )).classes('w-2/3').style('position: absolute; bottom: 10px;')
            

        with ui.column().classes(_button_column_classes):
            ui.button("Loader Snipet",icon="code", on_click=snipet.open).classes("w-full")
            with ui.dropdown_button("Actions", icon="menu",auto_close=False).classes("w-full gap-0"):
                download_button = ui.button("Download selected" if len(selected_parts)>0 else "Download", icon="download", on_click=on_download).classes("w-full").props(f'color={"green" if info["downloaded"] and len(selected_parts)==0 else ""}')
                del_button=ui.button("Remove selected" if len(selected_parts)>0 else "Remove data", icon="delete", on_click=dialog.open).classes("w-full").props('color="red"')
                if len(selected_parts)==0:
                    if info["downloaded"]:
                        download_button.disable()
                    else:
                        del_button.disable()



        with ui.scroll_area().classes(_info_list_classes):
            if len(selected_parts)>0:
                ui.label(f"{len(selected_parts)} partition(s) selected").classes('p-3')
            else:
                show_partition_info_list(metadata, (name, subs, part))


def show_partitions(views, metadata, path):
    name, subs = path
    dataview, infoview = views["dataview"], views["infoview"]
    dataview.clear()
    infoview.clear() 
    viewing_part = Mutable()
    columns, rows = partition_table(metadata["datasets"][name]["subsets"][subs])
    with dataview:
        table = ui.table(columns=columns, rows=rows, 
                        row_key='name',
                        selection='multiple',
                        pagination={'rowsPerPage': 10, 'sortBy': 'downloaded', 'descending':True, 'page': 1}
                        ).classes('w-full sticky-header-table')
        table.on('rowClick', lambda e: (
            (viewing_part.set(e.args[-2]['name'])),
            show_partition_info(views, metadata, (name, subs, e.args[-2]['name']), [r['name'] for r in table.selected])))
        with table.add_slot('top'):
            backbutton = ui.button(icon="arrow_back", on_click=lambda: (
                show_subsets(views, metadata, name),
                show_subset_info(views, metadata, path)
                )).style('margin-right:50px;')
            with ui.input(placeholder='Search').props('type=search rounded outlined dense clearable').classes('w-1/3').bind_value(table, 'filter').add_slot('append'):
                ui.icon('search')
            ui.label(f"{name}/{subs}").style(_title_style)
        table.on_select(lambda: show_partition_info(views, metadata, (name, subs, viewing_part.get()), [r['name'] for r in table.selected]))

def show_schema(views, metadata, path):
    import glob
    from PIL.JpegImagePlugin import JpegImageFile

    name, subs = path
    infoview = views["infoview"]
    infoview.clear()
    info = metadata["datasets"][name]["subsets"][subs]

    download_path = os.path.abspath(os.path.join(DATA_DIR, info["path"]))
    parquet_file = glob.glob(download_path+"/*")[0]
    schema = read_schema(parquet_file)
    datastream = iter(stream_dataset(name, subs, download_if_missing=False, 
                                     batch_size = webui_config.n_preview_samples))
    batch = Mutable(process_samples(name, next(datastream)))

    def on_click_sample(index):
        iloc = Mutable(1)
        sample_content.clear()

        field_ids = [index] if index>-1 else list(range(len(schema.names)))
        def fill_content(fields=None):
            gridview.clear()
            if fields is None:
                fields = [schema.names[i] for i in field_ids]
            else:
                field_ids.clear()
                field_ids.extend([schema.names.index(f) for f in fields])
            with gridview:
                ui.label("Field").style('font-weight: bold')
                ui.label("Sample").style('font-weight: bold')
                for field in fields:
                    ui.label(field)
                    sample = batch.v[field][iloc.v-1]
                    if type(sample)==JpegImageFile:
                        ui.image(sample).classes('w-[300px]')
                    else:
                        ui.label(str(sample))            

        with sample_content:
            with ui.scroll_area().classes('w-full h-[500px]'):
                gridview = ui.grid(columns="auto 1fr").classes('w-full no-wrap')
            with ui.row().classes('w-full items-top no-wrap h-auto p-1'):
                ui.select(schema.names, multiple=True, 
                          value=[schema.names[i] for i in field_ids], label='fields',
                          on_change=lambda e:fill_content(e.value)).classes('w-1/3').props('use-chips')
                with ui.row().classes('w-2/3 items-center no-wrap h-auto p-3'):
                    ui.slider(min=1, max=webui_config.n_preview_samples, on_change=fill_content).bind_value(iloc, 'v').classes('w-2/3 px-2 py-0')
                    ui.number(min=1, max=webui_config.n_preview_samples).bind_value(iloc, 'v').classes('px-2 py-0')
                    ui.button(icon='refresh',on_click=lambda:(
                        batch.set(process_samples(name, next(datastream))),
                        fill_content()
                    )).classes('p-3')

        sampleview.open()

    with infoview:
        with ui.dialog() as sampleview, ui.card().classes('items-center w-[1000px] h-[650px]').style('max-width: none; max-height: none'):
            sample_content = ui.column().classes('p-0 w-full items-center')

        with ui.scroll_area().classes(f'w-full h-[{_view_height}]'):
            with ui.row().classes('h-full items-center'):
                backbutton = ui.button(icon="arrow_back", on_click=lambda: show_subset_info(views, metadata, path)).classes('m-3')
                ui.label(subs).style("font-size:130%; font-weight:bold")
            with ui.column().classes('items-center p-5 gap-2 w-full'):
                ui.button("preview samples",icon="find_in_page", on_click= lambda:on_click_sample(-1)).classes('w-full')
            cols = [
                {'name': 'index', 'label': 'index', 'field': 'index', 'required': True, 'align': 'center', 'sortable': True},
                {'name': 'field', 'label': 'field', 'field': 'field', 'sortable': True, 'align': 'left'},
                {'name': 'dtype', 'label': 'dtype', 'field': 'dtype', 'sortable': True, 'align': 'left'},
            ]
            rows = [dict(index=i,field=field,dtype=str(dtype)) for i, (field, dtype) in enumerate(zip(schema.names, schema.types))]
            with ui.scroll_area().classes('w-full h-[600px]'):
                table = ui.table(columns=cols, rows=rows,
                            row_key='index').classes('w-full py-3 px-5')
                table.on('rowClick', lambda e: on_click_sample(e.args[-2]['index']))


def show_subset_info(views, metadata, path):
    name, subs = path
    dataview, infoview = views["dataview"], views["infoview"]
    infoview.clear()        

    async def on_download():
        n = ui.notification(timeout=None)
        n.message = 'Downloading : See progress on the server'
        n.spinner = True
        await asyncio.sleep(0.1)
        async def coro():
            download(name, subset=subs, force_redownload=False)
        task = asyncio.create_task(coro())
        await task

        n.message = 'Done!'
        n.spinner = False
        metadata["datasets"]=load_meta()["datasets"]
        show_subsets(views, metadata, path[0])
        await asyncio.sleep(2)
        n.dismiss()

    async def on_remove():
        n = ui.notification(timeout=None)
        n.message = 'Removing data ...'
        n.spinner = True
        await asyncio.sleep(0.1)
        async def coro():
            remove(name, subset=subs, force_remove=True)
        task = asyncio.create_task(coro())
        await task

        n.message = 'Done!'
        n.spinner = False
        metadata["datasets"]=load_meta()["datasets"]
        show_subsets(views, metadata, path[0])
        await asyncio.sleep(2)
        n.dismiss()

    info = metadata["datasets"][name]["subsets"][subs]

    def on_click_schema():
        if compute_subset_download(info)<=0:
            ui.notify("Schema not available until at least one partition is downloaded.")
        else:
            show_schema(views, metadata, path)

    with infoview:
        with ui.dialog() as dialog, ui.card().classes('items-center'):
            ui.label('You are about to remove the downloaded data.')
            ui.markdown('**Are you sure?**')
            with ui.grid(columns=2).classes('w-full items-center'):
                ui.button('Yes', icon="delete", on_click=on_remove).classes('w-full').props(f'color=red')
                ui.button('No', on_click=dialog.close).classes('w-full')

        tab_names = ['Stream', 'Full']
        with ui.dialog() as snipet, ui.card().classes('items-center').style(_snipet_style):
            codemirrors = []
            with ui.tabs().classes('w-full') as tabs:
                codemirrors.append(ui.tab(tab_names[0]).classes('w-full'))
                codemirrors.append(ui.tab(tab_names[1]).classes('w-full'))
            with ui.tab_panels(tabs, value=tab_names[0]).classes('w-full'):
                with ui.tab_panel(tab_names[0]).classes('w-full'):
                    codemirrors[0] = ui.codemirror(
                        stream_load_code_snipet(name,subs),
                                              line_wrapping=True, language='Python').classes('h-full')
                with ui.tab_panel(tab_names[1]).classes('w-full'):
                    codemirrors[1] = ui.codemirror(
                        full_load_code_snipet(name,subs), 
                                              line_wrapping=True, language='Python').classes('h-full')

            ui.button('Copy', 
                    on_click=lambda: (
                        pyperclip.copy(codemirrors[tab_names.index(tabs.value)].value),
                        ui.notify("Copied to clipboard"),
                        snipet.close()
                    )).classes('w-2/3').style('position: absolute; bottom: 10px;')

        with ui.column().classes(_button_column_classes):
            ui.button("Show partitions",icon="arrow_forward",on_click=lambda: show_partitions(views, metadata, path)).classes("w-full")
            downloaded = compute_subset_download(info)

            ui.button("Loader Snipet",icon="code", on_click=snipet.open).classes("w-full")
            ui.button("Show schema", icon="hub", on_click=on_click_schema).classes("w-full")

            with ui.dropdown_button("Actions", icon="menu",auto_close=False).classes("w-full"):
                download_button = ui.button("Download",icon="download", on_click=on_download).classes("w-full").props(f'color={"green" if downloaded==len(info["partitions"]) else ""}')
                del_button=ui.button("Remove data",icon="delete", on_click=dialog.open).classes("w-full").props('color="red"')
                if downloaded<=0:
                    del_button.disable()
                if downloaded==len(info["partitions"]):
                    download_button.disable()

        with ui.scroll_area().classes(_info_list_classes):
            show_subset_info_list(views, metadata, path)

def show_subsets(views, metadata, name):
    dataview, infoview = views["dataview"], views["infoview"]

    dataview.clear()
    infoview.clear()
    columns, rows = subset_table(metadata["datasets"][name])

    with dataview:            
        table = ui.table(columns=columns, rows=rows, 
                         row_key='name',
                         pagination={'rowsPerPage': 10, 'sortBy': 'downloaded', 'descending':True, 'page': 1}
                         ).classes('w-full sticky-header-table')

        table.on('rowClick', lambda e: show_subset_info(views, metadata, (name,e.args[-2]['name'])))
        with table.add_slot('top'):
            backbutton = ui.button(icon="arrow_back", on_click=lambda: (
                show_datasets(views, metadata),
                show_dataset_info(views, metadata, name)
                )).style('margin-right:50px;')
            with ui.input(placeholder='Search').props('type=search rounded outlined dense clearable').classes('w-1/3').bind_value(table, 'filter').add_slot('append'):
                    ui.icon('search')
            ui.label(f"{name}").style(_title_style)

def show_dataset_info(views, metadata, name):
    dataview, infoview = views["dataview"], views["infoview"]
    infoview.clear()

    with infoview:
        with ui.column().classes(_button_column_classes):
            ui.button("Show subsets",icon="arrow_forward",on_click=lambda: show_subsets(views, metadata, name)).classes("w-full")
        with ui.scroll_area().classes(_info_list_classes):
            show_dataset_info_list(views, metadata, name)


def show_datasets(views, metadata):
    dataview, infoview = views["dataview"], views["infoview"]
    dataview.clear()
    infoview.clear()
    columns, rows = dataset_table(metadata)
    with dataview:
        table = ui.table(columns=columns, rows=rows, 
                        row_key='name',
                        pagination={'rowsPerPage': 10, 'sortBy': 'name', 'page': 1}
                        ).classes('w-full sticky-header-table')
            
        table.on('rowClick', lambda e: show_dataset_info(views, metadata, e.args[-2]['name']))
        with table.add_slot('top'):                        
            with ui.input(placeholder='Search').props('type=search rounded outlined dense clearable').classes('w-1/3').bind_value(table, 'filter').add_slot('append'):
                ui.icon('search')

def show(context):
    print("[INFO] reading metafiles")
    metadata = load_meta()
    context.clear()
    views = dict()
    with context:
        dataview = ui.column().classes(f'w-3/4 h-[{_view_height}]')
        views["dataview"] = dataview
        with ui.card().classes(f'theme-color w-1/4 h-[{_view_height}]'):
            infoview = ui.column().classes(f'w-full h-full px-0 py-0 items-center')
        views["infoview"] = infoview
    show_datasets(views, metadata)