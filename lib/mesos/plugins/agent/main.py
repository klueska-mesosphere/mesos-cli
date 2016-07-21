import json
import sys
from socket import error as socket_error
import urllib2

import mesos.config as config
import mesos.util

from mesos.exceptions import CLIException
from mesos.plugins import PluginBase

PLUGIN_CLASS = "Agent"
PLUGIN_NAME = "agent"

VERSION = "Mesos CLI Agent Plugin 1.0"

SHORT_HELP = "Agent specific commands for the Mesos CLI"


class Agent(PluginBase):

    COMMANDS = {
        "ping" : {
            "arguments" : [],
            "flags" : {
                "--addr=<addr>" : "IP and port of agent [default: {ip}:{port}]"
                                  .format(ip=config.AGENT_IP,
                                          port=config.AGENT_PORT)
            },
            "short_help" : "Check Health of a running agent",
            "long_help"  :
                """
                Sends a HTTP healthcheck request and returns the result.
                """
        },
        "state" : {
            "arguments" : ["[<field>...]"],
            "flags" : {
                "--addr=<addr>" : "IP and port of agent [default: {ip}:{port}]"
                                  .format(ip=config.AGENT_IP,
                                          port=config.AGENT_PORT)
            },
            "short_help" : "Get Agent State Informtation",
            "long_help"  :
                """
                Get the agent state from the /state endpoint. If no <field> is
                supplied, it will display the entire state json. A field may be
                parsed from the state json to get its value. The format is
                field or index seperated by a \'.\'
                So for example, getting the work_dir from flags is:
                flags.work_dir
                Getting checkpoint information for the first framework would be:
                frameworks.0.checkpoint

                Multiple fields can be parsed from the same command.
                I.e. flags.work_dir id
                """
        }
    }

    def __setup__(self, command, argv):
        pass

    def __autocomplete__(self, command, current_word, argv):
        return []

    def isInt(self, num):
        try:
            int(num)
            return True
        except ValueError:
            return False

    def __parse_json(self, fields, json_info):
        split_fields = fields.split(".")
        json_sub = json_info

        for field in split_fields:
            if isinstance(json_sub,dict):
                if self.isInt(field):
                    raise CLIException("JSON is not a list, "
                                        "not expecting index!")
                if field in json_sub:
                    json_sub = json_sub[field]
                else:
                    raise CLIException("JSON field : {field} not found!"
                                        .format(field=field))
            elif isinstance(json_sub,list):
                if not self.isInt(field):
                    raise CLIException("JSON is a list,"
                                        " not expecting non-integer!")
                index = int(field)
                if index >= len(json_sub):
                    raise CLIException("List index out of bound!")
                json_sub = json_sub[index]
            else:
                raise CLIException("No further sub-fields for : {field}"
                                    .format(field=field))
                return json_sub

        return json_sub

    def ping(self, argv):
        httpResponseCode = None;
        try:
            httpResponseCode = ( urllib2.urlopen("http://"+argv["--addr"]
                                                    +"/health").getcode() )
        except Exception as exception:
            raise CLIException("Could not establish connection with agent:"
                                " {error}".format(error=exception))

        if httpResponseCode == 200 :
            print("Agent Healthy!")
        else:
            print("Agent not healthy!")

    def state(self,argv):
        try:
            state = mesos.util.hit_endpoint(argv["--addr"], "/state")
        except Exception as exception:
            raise CLIException("Unable to read from '/state' endpoint: {error}"
                               .format(error=str(exception)))

        if len(argv["<field>"]) == 0:
            print(json.dumps(state,indent=2))
            return

        for arg in argv["<field>"]:
            try:
                result = self.__parse_json(arg, state)
            except Exception as exception:
                print ("Error parsing json for {field} : {error}"
                        .format(field=arg,
                                error=exception))
                continue
            print (json.dumps(result,indent=2))
