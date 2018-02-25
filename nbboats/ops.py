import json
from shapely.geometry import shape
from rasterio import features
import requests
import pandas as pd
import numpy as np
from cStringIO import StringIO
from skimage import filters, morphology, measure


# CONSTANTS
SYDNEY_WEATHER_DATA = 'https://s3.amazonaws.com/gbdx-training/counting_boats/sydney_temp_history.csv'


# FUNCTIONS
def read_df_from_url(url):

    r = requests.get(url)
    df = pd.read_csv(StringIO(r.content))

    return df


def binary_threshold(img):

    img[np.isnan(img)] = 0
    simage = filters.gaussian(img, preserve_range=True)
    sthresh = filters.threshold_otsu(simage)
    binary = simage >= sthresh

    return binary


def m2_to_cells(area_m2, image):

    cell_height_m = image.ipe.metadata['image']['groundSampleDistanceMeters']
    cell_area_m2 = cell_height_m ** 2
    n_cells = np.round((area_m2 / cell_area_m2)).astype('int64')

    return n_cells


def calc_water_index(catalog_image):

    water_index = (catalog_image[7, :, :] - catalog_image[0, :, :]) / (catalog_image[7, :, :] + catalog_image[0, :, :])

    return water_index


def segment_land_water_and_boats(catalog_image, min_feature_size_m2=400000.):

    min_feature_size_cells = m2_to_cells(min_feature_size_m2, catalog_image)
    # convert image to simple binary water mask
    water_simple = binary_threshold(calc_water_index(catalog_image))
    # remove small holes
    water_no_holes = morphology.remove_small_holes(water_simple, min_feature_size_cells)
    # remove small objects
    water_only = morphology.remove_small_objects(water_no_holes, min_feature_size_cells, connectivity=2)
    # find just the potential boats
    boats_only = water_no_holes.astype('int') - water_only.astype('int')
    # add up to a single layer
    boats_land_and_water = boats_only * 2 + water_only

    return boats_land_and_water


def filter_boats(labels):

    boat_labels = [p.label for p in measure.regionprops(labels) if p.label <> 0 and p.solidity > 0.9]
    boats = labels * np.isin(labels.ravel(), boat_labels, assume_unique=False, invert=False).reshape(labels.shape)

    return boats


def clean_boats(boats_candidates_mask):

    boats_candidates_labels = morphology.label(boats_candidates_mask)
    boats = filter_boats(boats_candidates_labels)

    return boats


def segment_boats(catalog_image):

    image_segmented = segment_land_water_and_boats(catalog_image)
    boats_possible = image_segmented == 2
    boats = clean_boats(boats_possible)

    return boats


def to_geojson(l):
    g = {'crs'     : {u'properties': {u'name': u'urn:ogc:def:crs:OGC:1.3:CRS84'}, 'type': 'name'},
         'features': [{'geometry': d['geometry'].__geo_interface__, 'properties': d['properties'], 'type': 'Feature'}
                      for d in l],
         'type'    : u'FeatureCollection'}

    gj = json.dumps(g)

    return gj


def labels_to_polygons(labels_array, image_affine, ignore_label=0):
    # create polygon generator object
    polygon_generator = features.shapes(labels_array.astype('uint8'),
                                        mask=labels_array <> ignore_label,
                                        transform=image_affine)
    # Extract out the individual polygons, fixing any invald geometries using buffer(0)
    polygons = [{'geometry': shape(g).buffer(0), 'properties': {'id': v}} for g, v in polygon_generator]

    return polygons








