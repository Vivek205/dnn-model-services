import sys
import logging

import multiprocessing

import grpc
import concurrent.futures as futures

import service.common

# Importing the generated codes from buildproto.sh
import service.service_spec.voice_cloning_pb2_grpc as grpc_bt_grpc
from service.service_spec.voice_cloning_pb2 import Output

logging.basicConfig(level=10, format="%(asctime)s - [%(levelname)8s] - %(name)s - %(message)s")
log = logging.getLogger("voice_cloning_service")


def mp_clone(audio_url, audio, sentence, return_dict):
    import service.voice_cloning as vc
    return_dict["response"] = vc.clone(audio, audio_url, sentence)


# Create a class to be added to the gRPC server
# derived from the protobuf codes.
class RealTimeVoiceCloningServicer(grpc_bt_grpc.RealTimeVoiceCloningServicer):
    def __init__(self):
        # Just for debugging purpose.
        log.debug("RealTimeVoiceCloningServicer created")

    # The method that will be exposed to the snet-cli call command.
    # request: incoming data
    # context: object that provides RPC-specific information (timeout, etc).
    @staticmethod
    def clone(request, context):
        manager = multiprocessing.Manager()
        return_dict = manager.dict()
        worker = multiprocessing.Process(
            target=mp_clone,
            args=(request.audio_url, request.audio, request.sentence, return_dict))
        worker.start()
        worker.join()
    
        response = return_dict.get("response", None)
        if not response or "error" in response:
            error_msg = response.get("error", None) if response else None
            log.error(error_msg)
            context.set_details(error_msg)
            context.set_code(grpc.StatusCode.INTERNAL)
            return Output()

        log.debug("clone({},{})={}".format(request.audio_url[:10],
                                           request.sentence[:10],
                                           len(response["audio"])))
        return Output(audio=response["audio"])


# The gRPC serve function.
#
# Params:
# max_workers: pool of threads to execute calls asynchronously
# port: gRPC server port
#
# Add all your classes to the server here.
def serve(max_workers=10, port=7777):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers), options=[
        ('grpc.max_send_message_length', 10 * 1024 * 1024),
        ('grpc.max_receive_message_length', 10 * 1024 * 1024)])
    grpc_bt_grpc.add_RealTimeVoiceCloningServicer_to_server(
        RealTimeVoiceCloningServicer(),
        server)
    server.add_insecure_port("[::]:{}".format(port))
    return server


if __name__ == "__main__":
    """
    Runs the gRPC server to communicate with the Snet Daemon.
    """
    parser = service.common.common_parser(__file__)
    args = parser.parse_args(sys.argv[1:])
    service.common.main_loop(serve, args)
