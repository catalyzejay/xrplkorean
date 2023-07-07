import json
from datetime import datetime

# from time import sleep
from pprint import pprint
from xrpl.clients import JsonRpcClient
from xrpl.wallet import generate_faucet_wallet
from xrpl.wallet import Wallet
from xrpl.models.requests import AccountObjects, AccountInfo
from xrpl.models.response import Response
from xrpl.models.transactions import Payment, EscrowCreate, EscrowFinish, EscrowCancel
from xrpl.utils import datetime_to_ripple_time
from xrpl.transaction import autofill_and_sign, send_reliable_submission
from xrpl.account import get_balance

from utils import Address

JSON_RPC_URL = "https://s.altnet.rippletest.net:51234"


class XrplAccount:
    """
    XrplAccount 클래스는 XRP Ledger와 상호작용하는 기능을 제공합니다.
    이는 새 지갑 생성, 기존 지갑 파일에서 지갑 로드, 특정 주소로 XRP 보내기를 포함합니다.

    Attributes:
        client: XRP Ledger와 상호작용하기 위한 JsonRpcClient 인스턴스입니다.
        wallet: 현재 지갑을 나타내는 Wallet 인스턴스입니다.
    """

    def __init__(self, client: JsonRpcClient, wallet_path: str = "") -> None:
        """
        XRPL 객체의 모든 필요한 속성을 구성합니다.

        Args:
            wallet_path (str): 지갑 정보를 저장하는 파일의 경로입니다.
        """
        self._client = client
        self._wallet: Wallet = None  # type: ignore
        if wallet_path != "":
            self.load_wallet(wallet_path)

    def generate_wallet(self, wallet_path: str) -> Wallet:
        """
        새 지갑을 생성하고 지갑 정보를 파일에 저장합니다.

        Args:
            wallet_path (str, optional): 지갑 정보를 저장할 파일의 경로입니다.
        """
        self._wallet = generate_faucet_wallet(self._client, debug=True)

        with open(wallet_path, "w", encoding="UTF-8") as file:
            json.dump(self._wallet.__dict__, file)

        return self._wallet

    def load_wallet(self, wallet_path: str) -> Wallet:
        """
        파일에서 지갑 정보를 로드하고 새 Wallet 인스턴스를 구성합니다.

        Args:
            wallet_path (str): 지갑 정보를 저장하는 파일의 경로입니다.
        """
        with open(wallet_path, "r", encoding="UTF-8") as file:
            wallet_info = json.load(file)

        self._wallet = Wallet(
            seed=wallet_info["seed"],
            sequence=wallet_info["sequence"],
            algorithm=wallet_info["algorithm"],
        )

        return self._wallet

    def get_wallet(self) -> Wallet:
        """
        Returns:
            Wallet: 현재 지갑입니다.
        """
        return self._wallet

    def get_classic_address(self) -> Address:
        """
        Returns:
            address: 지갑의 클래식 주소입니다.
        """
        return Address(self._wallet.classic_address)

    def fetch_balance(self) -> int:
        """
        현재 지갑의 잔액을 검색합니다.

        Returns:
            int: XRP로 표시된 현재 지갑의 잔액입니다.
        """
        if self._wallet is None:
            raise Exception("지갑이 로드되지 않았거나 생성되지 않았습니다.")

        return get_balance(self._wallet.classic_address, self._client)

    def get_account_objects(self) -> list[dict]:
        """
        Returns:
            list[dict]: 계정 객체의 목록입니다.
        """
        account_objects_request = AccountObjects(account=self.get_classic_address())
        account_objects = (self._client.request(account_objects_request)).result[
            "account_objects"
        ]
        return account_objects

    def get_account_info(self) -> dict:
        """
        Returns:
            dict: 계정 정보입니다.
        """
        account_info_request = AccountInfo(account=self.get_classic_address())
        account_info = (self._client.request(account_info_request)).result
        return account_info

    def get_escrow_objects(self) -> list[dict]:
        """
        Returns:
            list[dict]: 에스크로 객체의 목록입니다.
        """
        escrow_objects_request = AccountObjects(account=self.get_classic_address())
        escrow_objects = (self._client.request(escrow_objects_request)).result[
            "account_objects"
        ]
        return escrow_objects

    def send_xrp(self, destination_address: Address, amount: str | int) -> Response:
        """
        특정 주소로 XRP를 보냅니다.

        Args:
            destination_address (Address): XRP를 보낼 주소입니다.
            amount (str): 보낼 XRP의 양입니다.

        Returns:
            Response: XRP Ledger에서의 응답입니다.

        """
        payment_tx = Payment(
            account=self.get_classic_address(),
            amount=str(amount),
            destination=destination_address,
        )

        signed_payment_tx = autofill_and_sign(payment_tx, self._wallet, self._client)

        response = send_reliable_submission(signed_payment_tx, self._client)

        return response

    def create_escrow(
        self,
        destination_address: Address,
        amount: str | int,
        finish_after: datetime,
        cancel_after: datetime = None,  # type: ignore
    ) -> Response:
        """
        특정 주소로 에스크로 결제를 생성합니다.

        Args:
            destination_address (Address): 에스크로 결제를 보낼 주소입니다.
            amount (str | int): 보낼 XRP의 양입니다.
            finish_after (datetime): 에스크로를 완료할 수 있는 시간입니다.
            cancel_after (datetime, optional): 에스크로를 취소할 수 있는 시간입니다. 기본값은 None입니다.

        Returns:
            Response: XRP Ledger에서의 응답입니다.
        """
        finish_after = datetime_to_ripple_time(finish_after)  # type: ignore
        if cancel_after is not None:
            cancel_after = datetime_to_ripple_time(cancel_after)  # type: ignore

        create_tx = EscrowCreate(
            account=self.get_classic_address(),
            destination=destination_address,
            amount=str(amount),
            finish_after=finish_after,  # type: ignore
            cancel_after=cancel_after,  # type: ignore
        )

        signed_create_tx = autofill_and_sign(create_tx, self._wallet, self._client)
        create_escrow_response = send_reliable_submission(
            signed_create_tx, self._client
        )

        # account_objects_request = AccountObjects(account=self.wallet.classic_address)
        # account_objects = (self.client.request(account_objects_request)).result["account_objects"]

        # print("Escrow object exists in current account:")
        # print(account_objects)

        return create_escrow_response

    def finish_escrow(self, offer_sequence: int) -> Response:
        """
        에스크로 거래를 완료합니다.

        Args:
            offer_sequence (int): 거래의 시퀀스 번호입니다.

        Returns:
            Response: XRP Ledger에서의 응답입니다.
        """
        finish_tx = EscrowFinish(
            account=self.get_classic_address(),
            owner=self.get_classic_address(),
            offer_sequence=offer_sequence,
        )

        signed_finish_tx = autofill_and_sign(finish_tx, self._wallet, self._client)
        finish_escrow_response = send_reliable_submission(
            signed_finish_tx, self._client
        )

        return finish_escrow_response

    def cancel_escrow(self, offer_sequence: int) -> Response:
        """
        에스크로 거래를 취소합니다.

        Args:
            offer_sequence (int): 거래의 시퀀스 번호입니다.

        Returns:
            Response: XRP Ledger에서의 응답입니다.
        """
        cancel_tx = EscrowCancel(
            account=self.get_classic_address(),
            owner=self.get_classic_address(),
            offer_sequence=offer_sequence,
        )

        signed_cancel_tx = autofill_and_sign(cancel_tx, self._wallet, self._client)
        cancel_escrow_response = send_reliable_submission(
            signed_cancel_tx, self._client
        )

        return cancel_escrow_response

    def __str__(self) -> str:
        """
        XRPL 객체의 문자열 표현을 반환합니다.

        Returns:
            str: XRPL 객체를 나타내는 문자열입니다.
        """
        return f"XRPL\nclient_url={self._client.url}\nwallet=\n{self._wallet}"

    def __dict__(self) -> dict:
        """
        XRPL 객체의 사전 표현을 반환합니다.

        Returns:
            dict: XRPL 객체를 나타내는 사전입니다.
        """
        return {
            "client": self._client,
            "wallet": self._wallet,
        }


if __name__ == "__main__":
    xrpl_client = JsonRpcClient(JSON_RPC_URL)
    test_account = XrplAccount(client=xrpl_client, wallet_path="database/wallet.json")
    dest_account = XrplAccount(
        client=xrpl_client, wallet_path="database/destination.json"
    )

    pprint(test_account.get_account_info())


# TODO: Add functionality to check if the wallet is ready for the transaction
# TODO: Add delegation for the transaction
# TODO: Add functionality to check if the transaction is successful
# TODO: Dockerize the application
