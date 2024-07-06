import argparse
import socket
import logging
import signal
import sys
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf, BadTypeInNameException
from colorama import init, Fore, Style

try:
    import nmb.NetBIOS as NetBIOS
except ImportError:
    NetBIOS = None

init(autoreset=True)

class MyListener(ServiceListener):
    def __init__(self, zeroconf, debug):
        self.zeroconf = zeroconf
        self.debug = debug
        self.services = {}
        self.max_name_length = 0
        self.max_ip_length = 15  # IP addresses have a fixed length format

    def remove_service(self, zeroconf, service_type, name):
        if name in self.services:
            del self.services[name]
            print(f"{Fore.RED}Service {name} removed")

    def add_service(self, zeroconf, service_type, name):
        self.update_service(zeroconf, service_type, name)

    def update_service(self, zeroconf, service_type, name):
        try:
            formatted_type = self.format_service_type(service_type)
            formatted_name = self.format_service_name(name)
            if self.debug:
                print(f"{Fore.YELLOW}Attempting to get service info for type: {formatted_type}, name: {formatted_name}")
            info = zeroconf.get_service_info(formatted_type, formatted_name)
            if info:
                address = socket.inet_ntoa(info.addresses[0]) if info.addresses else None
                if address:
                    device_name = self.resolve_device_name(address)
                    self.services[name] = address
                    self.max_name_length = max(self.max_name_length, len(name))
                    print(self.format_output(name.strip(), address.strip(), device_name.strip()) + '\r')
                else:
                    print(f"{Fore.YELLOW}Service {name} has no address")
            else:
                print(f"{Fore.YELLOW}No info found for service {name}")
        except BadTypeInNameException as e:
            if self.debug:
                print(f"{Fore.RED}BadTypeInNameException for type: {formatted_type}, name: {formatted_name} - {e}")

    def resolve_device_name(self, ip):
        name = None
        try:
            # Reverse DNS lookup
            name = socket.gethostbyaddr(ip)[0]
        except (socket.herror, socket.gaierror):
            pass

        if not name and NetBIOS:
            # NetBIOS lookup
            nb = NetBIOS.NetBIOS()
            try:
                name = nb.queryIPForName(ip, timeout=1)
            except Exception as e:
                if self.debug:
                    print(f"{Fore.RED}NetBIOS lookup failed for IP {ip}: {e}")
            finally:
                nb.close()

        return name if name else "Unknown"

    def format_service_type(self, service_type):
        if not service_type.endswith('.'):
            service_type += '.'
        return service_type

    def format_service_name(self, service_name):
        if not service_name.endswith('.'):
            service_name += '.'
        return service_name

    def format_output(self, name, address, device_name):
        name_spacing = ' ' * (60 - len(name) + 4)
        return (f"{Fore.GREEN}Service {name}{name_spacing}"
                f"{Fore.CYAN}IP: {address}{' ' * (self.max_ip_length - len(address) + 4)}"
                f"{Fore.MAGENTA}Name: {device_name}")

class ServiceTypeListener(ServiceListener):
    def __init__(self, zeroconf, debug):
        self.zeroconf = zeroconf
        self.debug = debug

    def add_service(self, zeroconf, service_type, name):
        formatted_type = self.format_service_type(name)
        print(f"{Fore.BLUE}Discovered service type: {formatted_type}")
        if self.debug:
            print(f"{Fore.YELLOW}Creating browser for type: {formatted_type}")
        ServiceBrowser(self.zeroconf, formatted_type, MyListener(self.zeroconf, self.debug))

    def update_service(self, zeroconf, service_type, name):
        pass

    def remove_service(self, zeroconf, service_type, name):
        pass

    def format_service_type(self, service_type):
        if not service_type.endswith('.'):
            service_type += '.'
        return service_type

def signal_handler(sig, frame):
    print('Exiting...')
    zeroconf.close()
    sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description="Service Finder using Zeroconf")
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()

    debug = args.debug
    if debug:
        print("Debug mode enabled")

    global zeroconf
    zeroconf = Zeroconf()
    type_listener = ServiceTypeListener(zeroconf, debug)

    print("Waiting for services to appear...")
    ServiceBrowser(zeroconf, "_services._dns-sd._udp.local.", type_listener)

    signal.signal(signal.SIGINT, signal_handler)
    signal.pause()

if __name__ == '__main__':
    main()

