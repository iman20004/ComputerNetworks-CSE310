import dns
import dns.resolver
import sys
import time

root_servers = ["198.41.0.4", "192.228.79.201", "192.33.4.12", "199.7.91.13", "192.203.230.10",
                "192.5.5.241", "192.112.36.4", "198.97.190.53", "192.36.148.17", "192.58.128.30",
                "193.0.14.129", "199.7.83.42", "202.12.27.33"]


def resolver(website: str, server: str):
    try:
        name = dns.name.from_text(website)
        message = dns.message.make_query(name, 1)
        response = dns.query.udp(message, server, 20)
    except:
        return None

    if response.rcode() != 0:  # Check for no errors
        return None
    else:
        # If answer section not empty
        if len(response.answer) != 0:
            # Check every answer one by one
            for ans in response.answer:
                # If particular ans is of type A, simply return
                if ans.rdtype == 1:
                    return ans

                # If particular ans is of type CNAME, then recursively check that in all servers
                elif ans.rdtype == 5:
                    for ans_item in ans.items:
                        cname = str(ans_item.target)
                        #for s in root_servers:
                        solution = resolver(cname, "198.41.0.4" )
                        if solution is not None:
                            return solution

                    return ans


        # Next, check additional section
        elif len(response.additional) != 0:
            # check for type A in additional
            for add in response.additional:
                if add.rdtype == 1:
                    # recursively check in all those new IP addresses
                    for add_item in add.items:
                        sol = resolver(website, str(add_item))
                        if sol is not None:
                            return sol
            return None

        # Lastly, check the authority section
        elif len(response.authority) != 0:
            webs = []
            # Get all the items form the authority section and store in array
            for authority in response.authority:
                for auth_item in authority.items:
                    webs.append(str(auth_item))

            solut = None
            # then recursively check the servers and the webs
            for web in webs:
                #for ser in root_servers:
                ret = resolver(web, "198.41.0.4")
                if ret is not None:
                    solut = resolver(website, ret[0])

            # if could not resolve any authoritative record, return None
            if solut is None:
                return None

        # Otherwise return nothing because we cant resolve
        else:
            return None

def print_ans(address):
    end = time.time()  # end time
    t_time = (end - start) * 1000  # total time to resolve in ms

    print("\nQUESTION SECTION:")
    print(domain + ".\t\tIN\tA")
    print("\nANSWER SECTION:")
    final = address.to_text().split()
    print(domain + ".\t" + final[1] + "\t" + final[2] + "\t" + final[3] + "\t" + final[4])
    print("\nQuery time: %.3f" % t_time + " ms")
    print("WHEN: " + when)


if __name__ == "__main__":

    # try to get the website name or throw error for unexpected input
    #try:
        #domain = str(sys.argv[1])
    #except:
        #print("Domain Invalid")
        #exit()

    when = time.ctime()
    start = time.time()
    domain = "fortest.jp"
    for root in root_servers:
        adr = resolver(domain, root)
        if adr is not None and len(adr) != 0:
            print_ans(adr)
            exit()

    print("Invalid domain")
