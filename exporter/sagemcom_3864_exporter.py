"""
Sagemcom F@ST 3864 Exporter for prometheus.
"""
import requests
import time

from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY

# Python 2/3 difference in import name
try:
    from HTMLParser import HTMLParser
except ImportError:
    from html.parser import HTMLParser

class TableParser(HTMLParser):
    """
    Retrieve a single table from HTML as an array of arrays
    """

    def __init__(self):
        HTMLParser.__init__(self)
        self.table = []
        self._tr = []
        self._data = ""

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.table = []
        elif tag == "tr":
            self._tr = []
        elif tag == "td" or tag == "th":
            self._data = ""

    def handle_endtag(self, tag):
        if tag == "tr":
            self.table.append(self._tr)
        elif tag == "td" or tag == "th":
            self._tr.append(self._data.strip())

    def handle_data(self, data):
        if not hasattr(self, '_data'):
            self._data = ''
        self._data = self._data + data

class SagemcomCollector(object):
    # Constants for table coordinates
    ADSL_COL_DOWN = 1
    ADSL_COL_UP = 2
    ADSL_ROW_RATE_ACTUAL = 14
    ADSL_ROW_RATE_ATTAINABLE = 10

    def __init__(self, base):
        self._base = base

    def _fetch_table(self, url):
        parser = TableParser()
        table_request = requests.get(url)
        if table_request.status_code is not 200:
            raise Exception("Failed request: " + url)
        parser.feed(table_request.text)
        if not hasattr(parser, 'table'):
            raise Exception("No table in response from: " + url)
        return parser.table

    def _extract_interface_stats(self, t, label, offset):
        header1 = t[0]
        header2 = t[1]
        stats_interfaces = t[2:]

        # Lan stats for bytes transferred, and packets transferred/errored/dropped
        rx_bytes = GaugeMetricFamily(label + '_network_receive_bytes', 'Received bytes for network interface', labels=['device'])
        tx_bytes = GaugeMetricFamily(label + '_network_send_bytes', 'Sent bytes for network interface', labels=['device'])
        rx_packets = GaugeMetricFamily(label + '_network_receive_packets', 'Received packets for network interface', labels=['device', 'disposition'])
        tx_packets = GaugeMetricFamily(label + '_network_send_packets', 'Sent packets for network interface', labels=['device', 'disposition'])

        # Add each interface
        for stats_interface in stats_interfaces:
            interface_name = stats_interface[0]
            # Transferred bytes
            rx_bytes.add_metric([interface_name], float(stats_interface[1 + offset]))
            tx_bytes.add_metric([interface_name], float(stats_interface[5 + offset]))
            # Transferred packets
            rx_packets.add_metric([interface_name, 'transfer'], float(stats_interface[2 + offset]))
            tx_packets.add_metric([interface_name, 'transfer'], float(stats_interface[6 + offset]))
            # Err packets
            rx_packets.add_metric([interface_name, 'error'], float(stats_interface[3 + offset]))
            tx_packets.add_metric([interface_name, 'error'], float(stats_interface[7 + offset]))
            # Drop packets
            rx_packets.add_metric([interface_name, 'drop'], float(stats_interface[4 + offset]))
            tx_packets.add_metric([interface_name, 'drop'], float(stats_interface[8 + offset]))

        yield rx_bytes
        yield tx_bytes
        yield rx_packets
        yield tx_packets

    def _collect_lan_stats(self):
        lan_data_table = self._fetch_table(self._base + 'statsifc.html')
        for stat in self._extract_interface_stats(lan_data_table, 'lan', 0):
            yield stat

    def _collect_wan_stats(self):
        wan_data_table = self._fetch_table(self._base + 'statswan.cmd')
        for stat in self._extract_interface_stats(wan_data_table, 'wan', 1):
            yield stat

    def _collect_xtm_stats(self):
        # Not currently used
        #t = self._fetch_table(self._base + 'statsxtm.cmd')
        # print(t)
        return []

    def _collect_adsl_stats(self):
        t = self._fetch_table(self._base + 'statsadsl.html')

        # Assemble stats
        rx_attaintable = GaugeMetricFamily('adsl_attainable_rate_down_kbps', 'ADSL Attainable Rate down (Kbps)')
        rx_attainable_val = t[SagemcomCollector.ADSL_ROW_RATE_ATTAINABLE][SagemcomCollector.ADSL_COL_DOWN]
        rx_attaintable.add_metric([], float(rx_attainable_val))
        yield rx_attaintable

        tx_attaintable = GaugeMetricFamily('adsl_attainable_rate_up_kbps', 'ADSL Attainable Rate up (Kbps)')
        tx_attainable_val = t[SagemcomCollector.ADSL_ROW_RATE_ATTAINABLE][SagemcomCollector.ADSL_COL_UP]
        tx_attaintable.add_metric([], float(tx_attainable_val))
        yield tx_attaintable

        rx_actual = GaugeMetricFamily('adsl_rate_down_kbps', 'ADSL Rate down (Kbps)')
        rx_actual_val = t[SagemcomCollector.ADSL_ROW_RATE_ACTUAL][SagemcomCollector.ADSL_COL_DOWN]
        rx_actual.add_metric([], float(rx_actual_val))
        yield rx_actual

        tx_actual = GaugeMetricFamily('adsl_rate_up_kbps', 'ADSL Rate up (Kbps)')
        tx_actual_val = t[SagemcomCollector.ADSL_ROW_RATE_ACTUAL][SagemcomCollector.ADSL_COL_UP]
        tx_actual.add_metric([], float(tx_actual_val))
        yield tx_actual

    def collect(self):
        for x in self._collect_lan_stats():
            yield x
        for x in self._collect_wan_stats():
            yield x
        for x in self._collect_adsl_stats():
            yield x
        for x in self._collect_xtm_stats():
            yield x

        yield GaugeMetricFamily('my_gauge', 'Help text', value=7)

collector_base = u"http://192.168.0.1/"
exporter_port = 8000

print("Configured to collect stats from '{}'".format(collector_base))
REGISTRY.register(SagemcomCollector(collector_base))

# Listen
start_http_server(exporter_port)
print("Listening on port {}".format(exporter_port))

# Go to sleep until Ctrl+C!
try:
    wait_time = 20.0
    while True:
        time.sleep(wait_time)
except KeyboardInterrupt:
    pass
