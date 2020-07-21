import subprocess


class CardanoNodeError(Exception):
    pass


class CardanoNode():

    def __init__(self, binary, topology, database_path, socket_path, port,
                 config, host_addr=None, kes_key=None, vrf_key=None, cert=None,
                 ssh=None):
        """Provides an interface for starting up a node locally or remote.
        """
        self.binary = binary
        self.topology = topology
        self.db_path = database_path
        self.socket_path = socket_path
        self.port = port
        self.config = config
        self.host_addr = host_addr
        self.kes_key = kes_key
        self.vrf_key = vrf_key
        self.cert = cert
        self.ssh = ssh
        self.debug = False

    def __exec(self, args):
        cmd = f"nohup {args} &> /dev/null &"
        if self.debug:
            print(cmd)
        if self.ssh is not None:
            self.ssh.open()
            self.ssh.run(cmd, warn=True, hide=True)
            self.ssh.close()
        else:
            subprocess.run(cmd.split())

    def start(self, mode="relay"):
        """Start the cardano-node (default relay mode)."""
        cmd = (
            f"{self.binary} run "
            f"--topology {self.topology} "
            f"--database-path {self.db_path} "
            f"--socket-path {self.socket_path} "
            f"--port {self.port} "
            f"--config {self.config} "
        )
        if self.host_addr is not None:
            cmd += f"--host-addr {self.host_addr} "
        if mode.lower() == "pool":
            cmd += (
                f"--shelley-kes-key {self.kes_key} "
                f"--shelley-vrf-key {self.vrf_key} "
                f"--shelley-operational-certificate {self.cert}"
            )
        self.__exec(cmd)
