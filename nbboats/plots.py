import jinja2
import json
import folium
from shapely.geometry import box
from gbdxtools import CatalogImage
from gbdxtools import IdahoImage
import numpy as np
from matplotlib import pyplot as plt, colors
import plotly.graph_objs as go


# CONSTANTS
COLORS_WATER_RGB = np.array([[8, 88, 158],
                             [120, 198, 121],
                             [255, 249, 35]])
COLORS_WATER_CMAP = colors.ListedColormap(COLORS_WATER_RGB / 255., name='from_list', N=None)
TMS_1030010067C11400 = 'https://s3.amazonaws.com/notebooks-small-tms/103001001B172A00/{z}/{x}/{y}.png'


# FUNCTIONS
def plot_boat_results(df):
    # Create a trace
    boats_trace = go.Scatter(x=df['date'],
                             y=df['n_boats'],
                             name='Boats')
    graph_data = [boats_trace]
    yaxis = dict(title='Number of Boats',
                 range=(0, max(df['n_boats'] + 50)))
    graph_layout = go.Layout(yaxis=yaxis, showlegend=False)
    fig = go.Figure(data=graph_data, layout=graph_layout)

    return fig


def folium_map(geojson_to_overlay, layer_name, location, style_function=None, tiles='Stamen Terrain', zoom_start=16,
               show_layer_control=True, width='100%', height='75%', attr=None, map_zoom=18, max_zoom=20, tms=False,
               zoom_beyond_max=None, base_tiles='OpenStreetMap', opacity=1):
    m = folium.Map(location=location, zoom_start=zoom_start, width=width, height=height, max_zoom=map_zoom,
                   tiles=base_tiles)
    tiles = folium.TileLayer(tiles=tiles, attr=attr, name=attr, max_zoom=max_zoom)
    if tms is True:
        options = json.loads(tiles.options)
        options.update({'tms': True})
        tiles.options = json.dumps(options, sort_keys=True, indent=2)
        tiles._template = jinja2.Template(u"""
        {% macro script(this, kwargs) %}
            var {{this.get_name()}} = L.tileLayer(
                '{{this.tiles}}',
                {{ this.options }}
                ).addTo({{this._parent.get_name()}});
        {% endmacro %}
        """)
    if zoom_beyond_max is not None:
        options = json.loads(tiles.options)
        options.update({'maxNativeZoom': zoom_beyond_max, 'maxZoom': max_zoom})
        tiles.options = json.dumps(options, sort_keys=True, indent=2)
        tiles._template = jinja2.Template(u"""
        {% macro script(this, kwargs) %}
            var {{this.get_name()}} = L.tileLayer(
                '{{this.tiles}}',
                {{ this.options }}
                ).addTo({{this._parent.get_name()}});
        {% endmacro %}
        """)
    if opacity < 1:
        options = json.loads(tiles.options)
        options.update({'opacity': opacity})
        tiles.options = json.dumps(options, sort_keys=True, indent=2)
        tiles._template = jinja2.Template(u"""
        {% macro script(this, kwargs) %}
            var {{this.get_name()}} = L.tileLayer(
                '{{this.tiles}}',
                {{ this.options }}
                ).addTo({{this._parent.get_name()}});
        {% endmacro %}
        """)

    tiles.add_to(m)
    if style_function is not None:
        gj = folium.GeoJson(geojson_to_overlay, overlay=True, name=layer_name, style_function=style_function)
    else:
        gj = folium.GeoJson(geojson_to_overlay, overlay=True, name=layer_name)
    gj.add_to(m)

    if show_layer_control is True:
        folium.LayerControl().add_to(m)

    return m


def get_idaho_tms_ids(image):
    ms_parts = {str(p['properties']['attributes']['idahoImageId']): str(
            p['properties']['attributes']['vendorDatasetIdentifier'].split(':')[1])
        for p in image._find_parts(image.cat_id, 'MS')}

    pan_parts = {str(p['properties']['attributes']['vendorDatasetIdentifier'].split(':')[1]): str(
            p['properties']['attributes']['idahoImageId'])
        for p in image._find_parts(image.cat_id, 'pan')}

    ms_idaho_id = [k for k in ms_parts.keys() if box(*IdahoImage(k).bounds).intersects(box(*image.bounds))][0]
    pan_idaho_id = pan_parts[ms_parts[ms_idaho_id]]

    idaho_ids = {'ms_id' : ms_idaho_id,
                 'pan_id': pan_idaho_id}
    return idaho_ids


def get_idaho_tms_url(source_catid_or_image, gbdx):
    if type(source_catid_or_image) == str:
        image = CatalogImage(source_catid_or_image)
    elif '_ipe_op' in source_catid_or_image.__dict__.keys():
        image = source_catid_or_image
    else:
        err = "Invalid type for source_catid_or_image. Must be either a Catalog ID (string) or CatalogImage object"
        raise TypeError(err)

    url_params = get_idaho_tms_ids(image)
    url_params['token'] = str(gbdx.gbdx_connection.access_token)
    url_params['z'] = '{z}'
    url_params['x'] = '{x}'
    url_params['y'] = '{y}'
    url_template = 'https://idaho.geobigdata.io/v1/tile/idaho-images/{ms_id}/{z}/{x}/{y}?bands=4,2,1&token={token}&panId={pan_id}'
    url = url_template.format(**url_params)

    return url


def plot_array(array, subplot_ijk, title="", font_size=18, cmap=None):
    sp = plt.subplot(*subplot_ijk)
    sp.set_title(title, fontsize=font_size)
    plt.axis('off')
    plt.imshow(array, cmap=cmap)


def plot_boat_results_with_temperature(merged_df):
    # Create a trace
    boats_trace = go.Scatter(x=merged_df['date'],
                             y=merged_df['n_boats'],
                             xaxis='x2',
                             yaxis='y2',
                             name='Boats',
                             marker={'color': '#2678B2'})

    # Create a trace
    temp_trace = go.Scatter(x=merged_df['date'],
                            y=merged_df['temp_f'],
                            name='Temperature',
                            marker={'color': '#FB7E28'})

    graph_data = [temp_trace, boats_trace]
    yaxis = dict(domain=(0, .45),
                 title='Temperature (F)',
                 range=(0, max(merged_df['temp_f'] + 10)))
    yaxis2 = dict(domain=(.55, 1),
                  title='Number of Boats',
                  range=(0, max(merged_df['n_boats'] + 50)),
                  anchor='x2')
    graph_layout = go.Layout(yaxis=yaxis,
                             yaxis2=yaxis2,
                             showlegend=False)
    fig = go.Figure(data=graph_data, layout=graph_layout)

    return fig

