import requests
import conf
import urllib2
import xml.etree.ElementTree as ET
import io


def get_min_temp_phrase_from_values(min_observed, min_forecast):
    if abs(min_forecast) != 1:
        degrees_text = "degrees"
    else:
        degrees_text = "degree"
    s = "The temperature tonight will be %s %s, " % (min_forecast, degrees_text)
    degrees_warmer_tonight = min_forecast - min_observed
    if abs(degrees_warmer_tonight) > 1:
        degrees_text = "degrees"
    else:
        degrees_text = "degree"

    if degrees_warmer_tonight == 0:
        s += "which is the same as last night"
    elif degrees_warmer_tonight > 0:
        s += "which is %s %s warmer than last night" % \
             (abs(degrees_warmer_tonight), degrees_text)
    else:
        s += "which is %s %s cooler than last night" % \
             (abs(degrees_warmer_tonight), degrees_text)
    return s


def get_min_observed_and_forecasted(bom_obs_url, bom_forecast_url, bom_forecast_area):
    # BOM observation data is available for several weather stations, and
    #  in several formats (including the JSON that we use here).
    #  e.g. http://www.bom.gov.au/products/IDN60901/IDN60901.94768.shtml
    r = requests.get(bom_obs_url)
    # this will only be used in the late afternoon and
    # min reading is usually about 5am on the same day.
    # Comes as a float, so let's round and cast
    min_obs = int(round(min([reading["air_temp"] for reading
                  in r.json()["observations"]["data"]])))

    # State forecast URLs are in XML format and are accessible from
    # http://www.bom.gov.au/info/precis_forecasts.shtml
    f = urllib2.urlopen(bom_forecast_url)
    forecast_report = io.StringIO(unicode(f.read()))
    tree = ET.parse(forecast_report)
    # Get the first (zeroth) minimum air temperature reading.
    # The current day will not have a minimum reading so this corresponds
    #  to tomorrow's minimum forecast temperature
    min_forecast = int(
        tree.findall("./forecast"
                     "/area[@aac='%s']"
                     "/forecast-period"
                     "/element[@type='air_temperature_minimum']" %
                     (bom_forecast_area,))[0].text)
    return min_obs, min_forecast

if __name__ == "__main__":
    print get_min_temp_phrase_from_values(*get_min_observed_and_forecasted(
        conf.LOCAL_BOM_OBSERVATIONS_URL,
        conf.STATE_BOM_FORECAST_URL,
        conf.LOCAL_BOM_FORECAST_AREA))
    # print get_min_temp_phrase_from_values(12, 0)
