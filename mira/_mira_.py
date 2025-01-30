#!/usr/bin/env python3

import argparse
import socket
import whois
import subprocess
import builtwith    
import re
import requests
import nmap
from threading import Thread, Lock
from queue import Queue
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


def strip_protocol(url):
    return url.replace('http://', '').replace('https://', '')


class DomainInfo:
    def __init__(self, target):
        self.target = target
        self.whois_data = []

    def get_ip_address(self):
        try:
            domain = re.sub(r'^https?://', '', self.target)
            ip_address = socket.gethostbyname(domain)
            self.whois_data.append(f"IP Address: {ip_address}\n")
        except Exception as e:
            self.whois_data.append(f"IP Address: Not found\nAn error occurred during IP lookup: {e}\n")


    def whois_lookup(self):
        try:
            w = whois.whois(self.target)
            whois_info = {
                'Domain Name': w.domain_name,
                'Registrar': w.registrar,
                'Creation Date': w.creation_date,
                'Expiration Date': w.expiration_date,
                'Last Updated': w.updated_date,
                'DNS Servers': w.name_servers,
                'Status': w.status,
                'Emails': w.emails,
                'DNSSEC': w.dnssec,
            }
            self.whois_data.append(whois_info)
        except Exception as e:
            self.whois_data.append(f"An error occurred during WHOIS lookup: {e}")

    def format_output(self):
        try:
            formatted_data = []
            for item in self.whois_data:
                if isinstance(item, dict):
                    for key, value in item.items():
                        formatted_data.append(f"{key}: {value}")
                else:
                    formatted_data.append(item.strip())
            return "\n".join(formatted_data)
        except Exception as e:
            return f"An error occurred when formatting the domain output: {e}"

    def get_domain_info(self):
        try:
            self.get_ip_address()
            self.whois_lookup()
            return self.format_output()
        except Exception as e:
            return f"An error occurred when retrieving domain information: {e}"

    def dns_look_up(target):
        try:
            return DomainInfo(target)
        except Exception as e:
            print(f"An error occurred during DNS lookup: {e}")


class WebScanner:
    def __init__(self, target, wordlist):
        self.target = target
        self.Target = strip_protocol(self.target)
        self.wordlist = wordlist
        self.q = Queue()
        self.list_lock = Lock()
        self.results = []
        
    def scan_directories(self): 
        print(f"Performing directory scan on {self.target}...\n")

        try:
            response = requests.get(self.target, timeout=5)
            response.raise_for_status()  
        except requests.exceptions.RequestException as e:
            print(f"[!] Error accessing {self.target}: {e}")
            return self.results
        
        soup = BeautifulSoup(response.text, 'html.parser')
        directories = set()

        try:
            for link in soup.find_all('a'):
                url = link.get('href')
                if url:
                    full_url = urljoin(self.target, url)
                    parsed_url = urlparse(full_url)

                    if parsed_url.path.endswith('/'):
                        directories.add(full_url)
        except Exception as e:
            print(f"An error occurred: {e}")

        for dir in directories:
            self.results.append(dir)

        return self.results
    
    def scan_subdomains(self):
        self.results.clear()
        print(f"Performing subdomain scan on {self.Target}...")
        
        q = Queue()
        self.results = []
        list_lock = Lock()
        
        with open(self.wordlist, 'r') as f:
            for subdomain in f:
                q.put(subdomain.strip())
        
        def scan():
            while True:
                subdomain = q.get()
                url = f"http://{subdomain}.{self.Target}"
                try:
                    requests.get(url)
                except requests.ConnectionError:
                    pass
                else:
                    with list_lock:
                        self.results.append(url)
                
                q.task_done()
        
        for t in range(10):
            worker = Thread(target=scan)
            worker.daemon = True
            worker.start()

        q.join()
        
        return self.results


class PortScanner:
    def __init__(self, target, ports):
        self.target = strip_protocol(target)
        self.ports = ports
        self.result = []  

    def basic_scan(self):
        print(f"Performing basic port scan on {self.target} for common ports...")
        try:
            nm = nmap.PortScanner()
            nm.scan(self.target, arguments=f'-p {self.ports}')
            self.scan_results(nm)
        except Exception as e:
            print(f"An error occurred: {e}")
        return self.result

    def scan_results(self, nm):
        try:
            for host in nm.all_hosts():
                self.result.append(f'Host: {host} ({nm[host].hostname()})')
                self.result.append(f'State: {nm[host].state()}')
                for proto in nm[host].all_protocols():
                    self.result.append(f'Protocol: {proto}')
                    for port in nm[host][proto].keys():
                        self.result.append(f'Port: {port}, State: {nm[host][proto][port]["state"]}')
        except Exception as e:
            print(f"An error occurred: {e}")


class WebsiteAnalyzer:
    def __init__(self, url):
        self.url = url
    
    def get_builtwith_technologies(self):
        try:
            website = builtwith.parse(self.url)
            return website
        except Exception as e:        
            print(f"An error occurred while parsing with BuiltWith: {e}")
            return {}

    def get_whatweb_technologies(self):
        try:
            result = subprocess.run(['whatweb', self.url], capture_output=True, text=True, check=True)
            if result.returncode == 0:
                return result.stdout
            else:
                print(f"Error: {result.stderr}")
                return ""
        except subprocess.CalledProcessError as e:
            print(f"CalledProcessError occurred: {e}")
            return ""
        except FileNotFoundError as e:
            print(f"FileNotFoundError occurred: {e}")
            return ""
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return ""

    @staticmethod
    def format_output(output):
        if not output:
            return ''
        pattern = r",(?![^\[\]]*\])"
        items = re.split(pattern, output)
        items = [item.strip() for item in items]
        formatted_output = "\n".join(items)
        return formatted_output

    def analyze(self):
        # Analyze website and print detected technologies
        print("\nDetected Software:")
        print("=================================")
        builtwith_technologies = self.get_builtwith_technologies()
        if builtwith_technologies:
            for key, value in builtwith_technologies.items():
                print(key + ":", ", ".join(value))

        print("---------------------------------")
        technologies = self.get_whatweb_technologies()
        if technologies:
            formatted_technologies = self.format_output(technologies)
            print(formatted_technologies)


def main():
    parser = argparse.ArgumentParser(description="Mira, a reconnaissance tool")
    parser.add_argument('-bi', '--basic-info', action='store_true', help="Basic Target Information")
    parser.add_argument('-ps', '--port-scan', action='store_true', help="Port Scan")
    parser.add_argument('-ds', '--dir-scan', action='store_true', help="Directory Scan")
    parser.add_argument('-ss', '--sub-scan', action='store_true', help="Subdomain Scan")
    parser.add_argument('-ts', '--tech-scan', action='store_true', help="Technology Scan")
    parser.add_argument('-t', '--target', type=str, help="Target URL", required=True)
    parser.add_argument('-p', '--ports', type=str, help="Ports to scan (e.g., 1-1024 or 22,80,443)")
    parser.add_argument('-wl', '--wordlist', type=str, help="Path to the wordlist", default="subdomains.txt")
    
    args = parser.parse_args()

    if args.target:
        pattern = re.compile(r"^(https?://)?(www\.)?([a-zA-Z0-9-]+(\.[a-zA-Z]{2,})+)$")
        match = pattern.match(args.target)
        
        if match:
            target = match.group(0)
            if not target.startswith("http"):
                target = "http://" + target
        else:
            print("Invalid URL. Please enter a valid URL.")
            return
    else:
        print("Please enter a target URL.")
        return
        
    if args.basic_info:
        try:
            analyse = DomainInfo.dns_look_up(target)
            if analyse:
                info = analyse.get_domain_info()
                print(info)
            else:
                print("Failed to perform DNS lookup.")
        except Exception as e:      
            print(f"An error occurred during basic scan: {e}")

    elif args.port_scan:
        try:
            scan = PortScanner(target, args.ports)
            results = scan.basic_scan()
            for result in results:
                print(result)
        except Exception as e:
            print(f"An error occurred during port scan: {e}")

    elif args.dir_scan:
        try:
            scanner = WebScanner(target, args.wordlist)
            directories = scanner.scan_directories()
            if directories:
                print("Directories found:")
                for directory in directories:
                    print(directory)
            else:
                print("No directories found.")
        except Exception as e:
            print(f"An error occurred during directory scan: {e}")
    
    elif args.sub_scan:
        try:
            scanner = WebScanner(target, args.wordlist)    
            subdomains = scanner.scan_subdomains()
            if subdomains:
                print("Subdomains found:")
                for subdomain in subdomains:
                    print(subdomain)
            else:
                print("No subdomains found.")
        except Exception as e:
            print(f"An error occurred during subdomain scan: {e}")

    elif args.tech_scan:
        try:
            analyzer = WebsiteAnalyzer(target)
            results = analyzer.analyze()
        except Exception as e:    
            print(f"An error occurred during technology scan: {e}")


if __name__ == "__main__":
    main()