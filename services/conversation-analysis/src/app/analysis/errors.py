class UnreadableCapture(Exception):
    """캡처에서 대화를 읽지 못했다. 상태와 유형을 추측하지 않는다."""


class LlmFailed(Exception):
    """모델 호출이 끝나지 않았다."""


class LlmRejected(LlmFailed):
    """모델이 스키마에 맞는 결과를 주지 않았다."""


class LlmQuotaExceeded(LlmFailed):
    """모델 제공사의 사용 한도를 다 썼다. 한도가 다시 채워질 때까지 실패한다."""


class LlmBusy(LlmFailed):
    """모델 제공사가 일시적으로 요청을 받지 못한다. 잠시 뒤 다시 시도하면 된다."""
