from mcp.server.fastmcp import FastMCP
import json
import ntcore

mcp = FastMCP("artemis-mcp-server")

"""
Network Tables 4 Wrapper with JSON return values and lazy subscriber/publisher initialization for MCP usage
"""
class NT4Client:
    def __init__(self, team=4152, tuning_prefix="/Tuning"):
        self.tuning_prefix = tuning_prefix
        self.inst = ntcore.NetworkTableInstance.create()
        self.inst.startClient4("artemis-nt4-client")
        self.inst.setServerTeam(team)
        self._multi_sub = ntcore.MultiSubscriber(self.inst, ["/"])
        self._subscribers: dict[str, ntcore.GenericSubscriber] = {}
        self._publishers: dict[str, ntcore.GenericPublisher] = {}

    def _subscriber(self, name: str) -> ntcore.GenericSubscriber:
        if name not in self._subscribers:
            self._subscribers[name] = self.inst.getTopic(name).genericSubscribe(ntcore.PubSubOptions(
                sendAll=True,
                keepDuplicates=True
            ))
        return self._subscribers[name]
    def _publisher(self, name: str, type_str: str) -> ntcore.GenericPublisher:
        if name not in self._publishers:
            self._publishers[name] = self.inst.getTopic(name).genericPublish(type_str)
        return self._publishers[name]

    async def isConnected(self) -> bool:
        return self.inst.isConnected()
    async def getConnections(self) -> str:
        return json.dumps({
            "connected" : self.inst.isConnected(),
            "connections" : [
                {
                    "remote_id" : c.remote_id,
                    "remote_ip" : c.remote_ip,
                    "remot_port" : c.remote_port,
                    "proto_version" : c.protocol_version,
                    "last_update" : c.last_update
                }
            for c in self.inst.getConnections()]
        })

    async def listTunableTopics(self) -> str:
        return await self._serializeTopicInfos(self.inst.getTopicInfo(self.tuning_prefix))
    async def listAllTopics(self) -> str:
        return await self._serializeTopicInfos(self.inst.getTopicInfo())
    async def _serializeTopicInfos(self, topic_infos: list[ntcore.TopicInfo]) -> str:
        return json.dumps([{
            "name" : topic.name,
            "properties": topic.properties,
            "type" : topic.type_str
        } for topic in topic_infos])
    _TYPE_MAP = {bool: "boolean", int: "int", float: "double", str: "string"}
    _MAKE_VALUE = {bool: ntcore.Value.makeBoolean, int: ntcore.Value.makeInteger, float: ntcore.Value.makeDouble, str: ntcore.Value.makeString}

    async def publishMultiple(self, names: list[str], values: list[str | int | float | bool]) -> str:
        return json.dumps([await self.publishTopicValue(name, value) for name, value in zip(names, values)])
    async def publishTopicValue(self, name: str, value: str | int | float | bool) -> str:
        type_str = self._TYPE_MAP.get(type(value))
        make_value = self._MAKE_VALUE.get(type(value))
        if type_str is None or make_value is None:
            raise ValueError(f"Unsupported value type: {type(value).__name__}")
        pub = self._publisher(name, type_str)
        pub.set(make_value(value))
        return json.dumps({"topic": name, "type": type_str, "value": value})

    async def refreshTopicsForReading(self, names: list[str]) -> str:
        for name in names: self._subscriber(name)
        return json.dumps(True)

    async def readMultipleTopics(self, names: list[str]) -> str:
        return json.dumps([await self.getTopicValue(name) for name in names])
    async def getTopicValue(self, name: str) -> dict:
        sub = self._subscriber(name)
        value = sub.get()
        return {
            "topic" : name,
            "value" : value.value(),
            "type" : self.inst.getTopic(name).getTypeString(),
            "timestamp" : value.time()
        }

    async def readMultipleTopicQueues(self, names: list[str]) -> str:
        return json.dumps([await self.readTopicQueue(name) for name in names])
    async def readTopicQueue(self, name: str) -> dict:
        sub = self._subscriber(name)
        data = sub.readQueue()
        if not data:
            return {
                "topic" : name,
                "samples" : [],
                "type" : self.inst.getTopic(name).getTypeString(),
                "timestamp" : None
            }
        return {
            "topic" : name,
            "samples" : [{"value": d.value(), "timestamp": d.time()} for d in data],
            "type" : self.inst.getTopic(name).getTypeString()
        }

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Artemis MCP Server")
    parser.add_argument("team", type=int, help="FRC team number")
    parser.add_argument("--tuning-prefix", default="/Tuning", help="NT4 tuning prefix (default: /Tuning)")
    args = parser.parse_args()

    global client
    client = NT4Client(team=args.team, tuning_prefix=args.tuning_prefix)
    mcp.run(transport="stdio")

client: NT4Client = None  # type: ignore

@mcp.tool()
async def is_connected() -> bool:
    """Returns whether the NT4 client is currently connected to the robot."""
    return await client.isConnected()

@mcp.tool()
async def get_connections() -> str:
    """Returns connection status and details for all active NT4 connections as JSON."""
    return await client.getConnections()

@mcp.tool()
async def list_all_topics() -> str:
    """Lists all known NT4 topics with their name, type, and properties as JSON."""
    return await client.listAllTopics()

@mcp.tool()
async def list_tunable_topics() -> str:
    """Lists all NT4 topics under the tuning prefix (default /Tuning) with name, type, and properties as JSON."""
    return await client.listTunableTopics()

@mcp.tool()
async def publish_multiple(names: list[str], values: list[str | int | float | bool]) -> str:
    """Publishes values to multiple NT4 topics in one call. names and values must be the same length."""
    return await client.publishMultiple(names, values)

@mcp.tool()
async def publish_topic_value(name: str, value: str | int | float | bool) -> str:
    """Publishes a single value to an NT4 topic. Type is inferred from the Python value type."""
    return await client.publishTopicValue(name, value)

@mcp.tool()
async def get_topic_value(name: str) -> str:
    """Returns the most recent value, type, and timestamp for a single NT4 topic as JSON."""
    return json.dumps(await client.getTopicValue(name))

@mcp.tool()
async def read_topic_queue(name: str) -> str:
    """Returns all queued samples since the last read for a single NT4 topic as JSON. Use for change detection or logging."""
    return json.dumps(await client.readTopicQueue(name))

@mcp.tool()
async def read_multiple_topics(names: list[str]) -> str:
    """Returns the most recent value for each of the given NT4 topics as a JSON array."""
    return await client.readMultipleTopics(names)

@mcp.tool()
async def refresh_topics_for_reading(names: list[str]) -> str:
    """Subscribes to the given topics so they begin buffering data. Call before reading topics that haven't been subscribed yet."""
    return await client.refreshTopicsForReading(names)

@mcp.tool()
async def read_multiple_topic_queues(names: list[str]) -> str:
    """Returns all queued samples since the last read for each of the given NT4 topics as a JSON array."""
    return await client.readMultipleTopicQueues(names)

if __name__ == "__main__":
    main()
