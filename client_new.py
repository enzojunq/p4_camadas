import time
import crcmod
import logging
from enlace import *

# Configuração da porta serial (altere para a porta correta)
serialName = "/dev/tty.usbmodem2101"
com1 = enlace(serialName)

# Configurações do EOP
EOP = b'\xAA\xBB\xCC'  # 3 bytes

# Configuração do logger
logging.basicConfig(filename='client_log.txt', level=logging.INFO, format='%(message)s')

def calculate_crc(payload):
    """Calcula o CRC-16 do payload."""
    crc16_func = crcmod.mkCrcFun(0x18005, rev=False, initCrc=0xFFFF, xorOut=0x0000)
    crc = crc16_func(payload)
    return crc.to_bytes(2, byteorder='big')

def log_event(action, message_type, total_bytes, packet_number=None, total_packets=None, crc=None):
    """Registra um evento no arquivo de log."""
    timestamp = time.strftime('%d/%m/%Y %H:%M:%S.%f', time.localtime())
    log_line = f"{timestamp} / {action} / {message_type} / {total_bytes}"
    if packet_number is not None and total_packets is not None:
        log_line += f" / {packet_number} / {total_packets}"
    if crc is not None:
        log_line += f" / {crc.hex()}"
    logging.info(log_line)

def create_datagram(packet_number, total_packets, payload, message_type=3, fake_payload_size=None):
    """Cria um datagrama com o cabeçalho, payload e EOP."""
    payload_size = fake_payload_size if fake_payload_size is not None else len(payload)
    crc = calculate_crc(payload)  # Calcula o CRC do payload

    # Cabeçalho tem 10 bytes
    head = (
        packet_number.to_bytes(2, 'big') +
        total_packets.to_bytes(2, 'big') +
        payload_size.to_bytes(2, 'big') +
        message_type.to_bytes(1, 'big') +
        b'\x00'*3 +  # Reservado
        crc  # Adiciona o CRC ao cabeçalho
    )
    return head + payload + EOP

def handshake():
    """Realiza o handshake inicial com o servidor."""
    # Enviar byte de sacrifício para eliminar "lixo"
    time.sleep(0.2)
    com1.sendData(b'00')  # Byte de sacrifício
    time.sleep(1)

    datagram = create_datagram(0, 0, b'', message_type=1)  # Tipo 1: Handshake
    com1.sendData(datagram)
    print("Cliente: Enviando mensagem de handshake...")
    log_event('envio', '1', len(datagram))  # Tipo 1: Handshake

    # Aguarda resposta do servidor
    response, _ = com1.getData(14)  # Ajuste o tamanho conforme necessário
    if response:
        message_type = response[6]
        log_event('receb', message_type, len(response))
        if message_type == 2:  # Tipo 2: ACK de handshake
            print("Cliente: Handshake bem-sucedido")
            return True
    print("Cliente: Handshake falhou")
    return False

def send_file(file_path):
    """Envia um arquivo fragmentado em pacotes."""
    with open(file_path, 'rb') as file:
        content = file.read()

    total_packets = (len(content) + 49) // 50  # Calcula o número total de pacotes
    packet_index = 0

    while packet_index < total_packets:
        start = packet_index * 50
        end = min((packet_index + 1) * 50, len(content))
        payload = content[start:end]

        # Simulando erros para testes
        erro_ordem = False
        erro_crc = False
        interrupcao = False

        # Simulando erro na ordem dos pacotes (pulando o pacote 2)
        if packet_index == 1 and erro_ordem:
            print("Cliente: Pulando o envio do pacote 2 para simular erro de ordem.")
            packet_index += 1
            continue

        # Simulando erro de CRC no pacote 3
        if packet_index == 2 and erro_crc:
            print("Cliente: Simulando erro de CRC no pacote 3.")
            payload = b'\x00' * len(payload)  # Altera o payload para gerar CRC diferente

        # Simulando interrupção após o pacote 4
        if packet_index == 3 and interrupcao:
            print("Cliente: Simulando interrupção na transmissão. Aguarde reconexão...")
            com1.disable()
            time.sleep(5)  # Aguarda 5 segundos
            com1.enable()
            print("Cliente: Reconexão feita. Retomando transmissão.")

        # Criar e enviar o datagrama
        datagram = create_datagram(packet_index + 1, total_packets, payload)
        com1.sendData(datagram)
        print(f'Cliente: Pacote {packet_index + 1} enviado \n')
        log_event('envio', '3', len(datagram), packet_index + 1, total_packets, calculate_crc(payload))

        # Aguardar ACK ou NACK
        response, _ = com1.getData(14)  # Ajuste o tamanho conforme necessário

        # Verifica se é ACK ou NACK
        if response:
            message_type = response[6]
            log_event('receb', message_type, len(response))
            if message_type == 4:  # Tipo 4: ACK
                print(f'Cliente: ACK recebido para pacote {packet_index + 1}')
                packet_index += 1  # Prossegue para o próximo pacote
            elif message_type in [5, 6]:  # Tipos 5 e 6: NACK
                print(f'Cliente: NACK recebido para pacote {packet_index + 1}. Reenviando...')
                # Não incrementa o índice, reenvia o mesmo pacote
        else:
            print(f'Cliente: Nenhuma resposta recebida. Tentando novamente...')
            # Pode implementar lógica de timeout ou tentativas

def main():
    try:
        com1.enable()

        handshake_successful = False

        while not handshake_successful:
            if handshake():
                handshake_successful = True
                file_path = 'arquivo.txt'  # Altere para o caminho correto do arquivo
                send_file(file_path)
            else:
                print("Servidor inativo. Tentar novamente? S/N")
                retry = input().lower()
                if retry != 's':
                    com1.disable()  # Desabilitar comunicação antes de sair
                    return
                else:
                    print("Tentando novamente o handshake...")

        com1.disable()
        print("Arquivo enviado com sucesso!")

    except Exception as e:
        print("Cliente: Ocorreu um erro:", e)
        com1.disable()

if __name__ == "__main__":
    main()
