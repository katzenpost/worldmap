#!/usr/bin/env python3

from six.moves.urllib.parse import urlparse
import asyncio
import geoip2.database
import geoip2
import cbor2
import matplotlib.pyplot as plt
import cartopy.io.img_tiles
import cartopy.crs
import cartopy.crs as ccrs
import click

from thinclient import ThinClient, Config

def get_nodes(doc):
    nodes = []
    for _, gatewayNode in enumerate(doc["GatewayNodes"]):
        nodes.append(cbor2.loads(gatewayNode))
    for _, serviceNode in enumerate(doc["ServiceNodes"]):
        nodes.append(cbor2.loads(serviceNode))
    for _, layer in enumerate(doc["Topology"]):
        for _, node in enumerate(layer):
            nodes.append(cbor2.loads(node))
    return nodes

def get_address_urls(nodes):
    urls = []
    for i, node in enumerate(nodes):
        addrs = node["Addresses"]
        if "tcp" in addrs:
            urls.append(addrs["tcp"])
        elif "tcp4" in addrs:
            urls.append(addrs["tcp4"])
        elif "quic" in addrs:
            urls.append(addrs["quic"])
        else:
            continue
    return urls

def get_ip_addrs(urls):
    ip_addrs = []
    for _, url in enumerate(urls):
        parsed_url = urlparse(url[0])
        ip = parsed_url.netloc.split(":")[0]
        ip_addrs.append(ip)
    return ip_addrs

def read_dirauth_ips(filepath):
    with open(filepath, 'r') as file:
        return [line.strip() for line in file if line.strip()]

def get_gps_coords(ip_addrs, geolite2_city_db_filepath):
    gps_coords = []
    with geoip2.database.Reader(geolite2_city_db_filepath) as reader:
        for _, ip in enumerate(ip_addrs):
            try:
                response = reader.city(ip)
                latitude = response.location.latitude
                longitude = response.location.longitude
                gps_coords.append((longitude, latitude))  # Store coordinates as (lon, lat)
            except geoip2.errors.AddressNotFoundError:
                print(f"Location not found for IP: {ip}")
    return gps_coords


def plot_world_map(diraut_gps_coords, mix_gps_coords, out_file):
    fig = plt.figure(figsize=(4, 2), facecolor="black")
    ax = plt.axes(projection=ccrs.Mollweide())
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.coastlines(color="white")
    ax.add_feature(cartopy.feature.BORDERS, linestyle='-', alpha=0.5)
    ax.add_feature(cartopy.feature.OCEAN, color="black")
    for lon, lat in mix_gps_coords:
        ax.plot(lon, lat, marker='o', color='red', markersize=3, transform=ccrs.PlateCarree())
    for lon, lat in diraut_gps_coords:
        ax.plot(lon, lat, marker='o', color='purple', markersize=4, transform=ccrs.PlateCarree())
    plt.savefig(out_file, dpi=200, bbox_inches="tight", pad_inches=0)
    print(f"wrote world map to {out_file}")


@click.command()
@click.option("--geolite2-db", "geolite2_city_db_filepath", default="GeoLite2-City.mmdb",
              show_default=True, help="Path to the GeoLite2 City database.")
@click.option("--dirauth-ips", "dirauth_ips_filepath", default=None,
              help="File containing the list of directory authority IP addresses, one address per line.")
@click.option("--output", "out_file", default="world_map.png", show_default=True,
              help="Output file name for the generated world map.")
def main(geolite2_city_db_filepath, dirauth_ips_filepath, out_file):
    asyncio.run(run_async(geolite2_city_db_filepath, dirauth_ips_filepath, out_file))

async def run_async(geolite2_city_db_filepath, dirauth_ips_filepath, out_file):
    cfg = Config()
    client = ThinClient(cfg)
    await client.start(asyncio.get_event_loop())
    doc = client.pki_document()
    client.stop()

    nodes = get_nodes(doc)
    urls = get_address_urls(nodes)
    ip_addrs = get_ip_addrs(urls)
    mix_gps_coords = get_gps_coords(ip_addrs, geolite2_city_db_filepath)

    # Get directory authority IPs if a filepath is provided
    dirauth_gps_coords = []
    if dirauth_ips_filepath:
        dirauth_ips = read_dirauth_ips(dirauth_ips_filepath)
        dirauth_gps_coords = get_gps_coords(dirauth_ips, geolite2_city_db_filepath)
    
    plot_world_map(dirauth_gps_coords, mix_gps_coords, out_file)
    print(doc.keys())

if __name__ == '__main__':
    main()
