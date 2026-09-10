# Microduck 자산 라이선스와 참가 조건

라이선스 원문 확인일: 2026-09-09. 공식 온라인 데모 연결 범위 추가: 2026-09-10. AWS GPU → 공식 MuJoCo/mjlab PPO → ONNX → 실물 Microduck 워크숍용 운영 기준이다. **법률 자문이나 개별 이용의 적법성 판단이 아니며, 참가자에게 새 권한을 부여하지 않는다.** 원문·확인 시각·해시는 [근거 JSON](licensing-evidence.json)에 기록했다.

**소프트웨어의 Apache-2.0과 3D 모델의 비상업 조건을 구분한다.** 자체 설명·코드·추상 구조도를 공개하는 것과, 실습에서 상류 로봇 자산을 취득·이용하는 것은 각각 확인해야 한다.

| 확인 대상 | 공식 근거와 한계 |
| --- | --- |
| `microduck_rl` 소프트웨어 | [README][rl-readme]와 [LICENSE][rl-license]: Apache-2.0. |
| `microduck_rl` 3D 모델 | README 원문: **“3D model files are licensed under Creative Commons BY-SA-NC.”** 적용 버전·법률문 링크·파일별 경계는 검토 자료에 명시되지 않았다. 임의로 `CC-BY-NC-SA-4.0`으로 확정하지 않는다. |
| `microduck` 런타임 | 루트 [LICENSE][rt-license]는 Apache-2.0. [README][rt-readme]는 학습 저장소를 연결한다. [벤더 라이선스][vendor]처럼 별도 조건도 있으므로 모든 파일을 Apache로 일괄 취급하지 않는다. |
| `NOTICE` | 두 고정 커밋의 전체 Git 트리(`truncated=false`)에서 `NOTICE`/`NOTICE.*` 파일을 찾지 못했다. 외부 의존성의 NOTICE까지 없다는 의미는 아니다. |
| 제품 안내·구매 | [공식 제품 페이지][product]의 “The whole software stack, permissively licensed”는 소프트웨어 설명이다. 3D 모델의 NC 예외를 해제하는 문구로 삼지 않는다. 제품 구매·[판매 약관][sales]과 디지털 자산 이용 권한의 관계도 별도 확인한다. |

참조 고정: `microduck_rl/develop` → `53b8971b61baf5b7f3c16d135dd7cac37623de4b` (2026-09-09 09:04:44 UTC), `microduck/main` → `5620aa214e6e304eec00d5c376ac81d3001fb7a3` (2026-09-08 19:05:42 UTC). 버전 미표기를 이유로 라이선스가 무효라고 판단하지 않는다.

**BY·NC·SA의 실무 의미.** README의 순서는 `BY-SA-NC`이며 CC의 통상 표기는 `BY-NC-SA`이다. [CC 공식 설명][cc-types]은 출처 표시(BY), 비상업 목적(NC), 변경물을 공유할 때 동일·허용되는 호환 조건 준수(SA)를 설명한다. 정확한 표시·변경 고지·공유 의무는 확인된 적용 버전의 법률문을 따라야 한다. 일반 설명 페이지는 Pollen 자산의 라이선스 버전을 지정하지 않는다.

**공개 소스의 포함 범위.** 이 워크숍은 직접 작성한 한국어 설명·운영 코드·추상 구조도와 공식 링크를 공개하는 방식으로 구성한다. 상류 메쉬/STL·CAD·MJCF/URDF 등 로봇 모델과 변환물, 상류 체크포인트·ONNX, 사진·영상·로고·모델 렌더 캡처는 포함하지 않는다. 자체 구조도도 원본 형상이나 사진을 추적·복제하지 않는다. 자산을 담은 AMI·컨테이너·EBS 스냅샷·공유 S3 패키지도 이 범위에서 제외한다. 이는 포함 정책이며 저장소 전체 내용에 대한 감사 결과는 아니다.

**공식 온라인 데모 연결.** `static/visuals/biped-3d.html`은 [Pollen Robotics의 공식 Microduck 시뮬레이터][simulator]를 임베드·링크한다. 제공자 앱은 `https://pollen-robotics-microduck-simulator.hf.space`에서 로드하며 메시·가중치·사진을 교재 배포물에 복사하지 않는다. 브라우저가 제공자 자산을 로드하므로 이를 자산을 전혀 취득·이용하지 않는 체험이라고 표현하지 않는다. 인터넷과 제공자 서비스 가용성이 필요하고, 임베드가 열리지 않을 때는 공식 Space에 직접 접속한다.

공개 Space의 임베드·링크는 모델의 NC 조건을 해소하거나 상업 이용권을 부여하지 않는다. 행사에서 데모를 사용하는 조건과 자산을 내려받아 학습·공유하는 권한은 각각 확인한다. 아래 자산 취득·학습 전 참가 조건과 `--asset-permission-confirmed` 게이트는 그대로 유지한다. 온라인 데모는 내 AWS GPU 학습·체크포인트 재생·실물 로봇 또는 모터 연결과 별개이며 워크샵 학습 결과의 증거로 사용하지 않는다.

Apache 소프트웨어 코드를 복사·수정하여 배포한다면 LICENSE 사본, 변경 표시, 기존 저작권·특허·상표·출처 고지와 해당 NOTICE를 보존한다([§4][rl-license]). 직접 작성한 소스의 라이선스가 상류 자산·벤더 코드·정책 가중치에 자동 적용되지는 않는다. Apache §6도 일반적인 상표 사용권을 부여하지 않는다.

**자산 취득 전 참가 조건.** 아래는 이 워크숍의 운영 전제이며 라이선스 문구에 없던 권한을 만들어 주는 절차가 아니다.

1. 참가자와 주최자는 사용 조직·목적·대가·영업/마케팅 연계·고객 PoC 여부 및 자산·공유 범위를 먼저 확인한다.
2. 운영자는 **(가)** 적용 자산의 라이선스 버전·법률문·범위와 해당 이용의 NC 적합성, 필요한 BY/SA 이행을 확인했거나, **(나)** 해당 이용을 허용하는 권리자의 명시적 서면 허가/별도 라이선스를 확보한 경우에만 자산 실습을 연다. 서면 허가는 참가·주최 조직, AWS 복제·저장·학습, ONNX 내보내기·실물 시연, 기간·공유 범위 및 필요한 배포를 실제로 포괄해야 한다.
3. 확인 날짜·담당자·고정 커밋·용도·라이선스/허가 참조와 범위를 비공개 기록으로 남긴다. 체크박스나 환경변수만으로 허가가 생기지는 않는다.
4. 이 확인은 **`git clone`, ZIP 다운로드, 의존성 설치나 cloud-init의 자동 자산 취득보다 먼저** 수행한다. 라이선스 버전·적용 범위 또는 허가가 미해결이면 취득 및 해당 자산을 사용하는 시뮬레이션·학습·배포 실습을 보류하고 자체 자료의 개념 설명·코드 읽기까지만 진행한다. 이번 조사는 권리자 허가를 취득하지 않았다.

**AWS·고객 세션에 적용할 때.** [CC의 NC 해설][cc-nc]과 [FAQ][cc-faq]은 주된 이용 목적이 상업적 이익이나 금전적 보상을 지향하는지를 본다. 유료 교육, AWS 영업·마케팅 행사, 고객 PoC, 사업상 이익을 위한 사내 교육은 NC 적합성을 자동 전제할 수 없다. 운영상 구체적 검토와 필요한 권한 확인 전 자산 실습을 열지 않는다. 반대로 회사 소속이라는 이유만으로 모든 이용이 위반인 것도 아니며, AWS 사용료 지불만으로 결론이 정해지지도 않는다. **무료 참가·교육 목적·개인 계정·공개 GitHub라는 사실만으로 허용되지 않는다.**

**개별 다운로드와 재배포.** 참가자가 공식 저장소에서 직접 받으면 워크숍 배포물에 자산을 포함하는 일을 피할 수 있다. 그러나 다운로드·복제·로딩·학습에 필요한 권한과 NC 조건은 여전히 검토해야 한다. 개인 다운로드는 상업 이용 제한의 우회 수단이 아니다. 복제본을 AMI나 S3로 나누는 행위는 추가 공유·배포 범위로 확인한다.

**학습 결과·ONNX·실물 시연.** 학습하거나 ONNX로 변환했다는 사실이 원래 자산의 이용 조건을 없애지는 않는다([CC 기술 이용 FAQ][cc-ai]). 반대로 학습 결과에 CC가 자동 전파된다고도 단정하지 않는다. 자체 학습 정책, 상류 사전 학습 정책, 렌더·영상 각각의 공개·고객 전달 가능성은 출처와 허가 범위를 별도 검토한다. 이 문서로 체크포인트/ONNX의 공개나 제품 구매에 따른 3D 자산의 상업 이용을 승인하지 않는다.

라이선스 원문 조사의 검토 범위는 공식 README·LICENSE·트리 메타데이터와 제품·판매·CC 안내의 텍스트다. 해당 조사에서는 메쉬·가중치·사진·영상을 다운로드하거나 설치하지 않았으며, 권리자 연락이나 외부 게시는 하지 않았다. 추가한 공식 Space 메타데이터 근거는 [출처](sources.md)에 기록한다. 온라인 데모의 실제 브라우저 검증은 별도 작업이며, 앱을 열면 브라우저가 제공자 자산을 로드한다.

[rl-readme]: https://github.com/pollen-robotics/microduck_rl/blob/53b8971b61baf5b7f3c16d135dd7cac37623de4b/README.md#L258-L261
[rl-license]: https://github.com/pollen-robotics/microduck_rl/blob/53b8971b61baf5b7f3c16d135dd7cac37623de4b/LICENSE
[rt-readme]: https://github.com/pollen-robotics/microduck/blob/5620aa214e6e304eec00d5c376ac81d3001fb7a3/README.md
[rt-license]: https://github.com/pollen-robotics/microduck/blob/5620aa214e6e304eec00d5c376ac81d3001fb7a3/LICENSE
[vendor]: https://github.com/pollen-robotics/microduck/blob/5620aa214e6e304eec00d5c376ac81d3001fb7a3/tof/vendor/LICENSE.txt
[product]: https://pollen-robotics.com/microduck
[sales]: https://pollen-robotics.com/general-terms-and-conditions-of-sales/
[cc-types]: https://creativecommons.org/share-your-work/cclicenses/
[cc-nc]: https://wiki.creativecommons.org/wiki/NonCommercial_interpretation
[cc-faq]: https://creativecommons.org/faq/#does-my-use-violate-the-noncommercial-clause-of-the-licenses
[cc-ai]: https://creativecommons.org/faq/#what-are-the-limits-on-how-cc-licensed-works-can-be-used-in-the-development-of-new-technologies-such-as-training-of-artificial-intelligence-software

[simulator]: https://huggingface.co/spaces/pollen-robotics/microduck-simulator
