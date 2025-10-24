package com.example.baseball

import android.annotation.SuppressLint
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCharacteristic
import android.os.Bundle
import android.widget.*
import androidx.activity.ComponentActivity
import com.example.baseball.R
import java.util.*

class ConnectedActivity : ComponentActivity() {

    companion object {
        lateinit var gatt: BluetoothGatt
        val CHAR_UUID: UUID = UUID.fromString("abcdef01-1234-5678-1234-56789abcdef0")
        val SERVICE_UUID: UUID = UUID.fromString("12345678-1234-5678-1234-56789abcdef0")
    }

    private val teamPlayers = mapOf(
        "LG" to mapOf(
// --- 포수 ---
            // --- LG 트윈스 ---
            "김범석" to "KIM_BEOMSEOK",
            "김성우" to "KIM_SEONGWOO",
            "김준태" to "KIM_JOONTAE",
            "박동원" to "PARK_DONGWON",
            "이주헌" to "LEE_JOOHEON",
            "이한림" to "LEE_HANLIM",

            "구본혁" to "KOO_BONHYUK",
            "김민수" to "KIM_MINSOO",
            "김성진" to "KIM_SEONGJIN",
            "김주성" to "KIM_JOOSEONG",
            "문보경" to "MOON_BOKYUNG",
            "문정빈" to "MOON_JEONGBIN",
            "손용준" to "SON_YONGJUN",
            "신민재" to "SHIN_MINJAE",
            "오스틴" to "AUSTIN",
            "오지환" to "OH_JIHWAN",
            "이영빈" to "LEE_YOUNGBIN",
            "이태훈" to "LEE_TAEHOON",
            "천성호" to "CHEON_SEONGHO",
            "김대원" to "KIM_DAEWON",

            "김현수" to "KIM_HYUNSOO",
            "김현종" to "KIM_HYEONJONG",
            "문성주" to "MOON_SEONGJOO",
            "박관우" to "PARK_GWANWOO",
            "박해민" to "PARK_HAEMIN",
            "서영준" to "SEO_YOUNGJUN",
            "송찬의" to "SONG_CHANEUI",
            "안익훈" to "AN_IKHOON",
            "최승민" to "CHOI_SEUNGMIN",
            "최원영" to "CHOI_WONYOUNG",
            "함창건" to "HAM_CHANGGEON",
            "홍창기" to "HONG_CHANGKI",
            "최명경" to "CHOI_MYUNGKYUNG",
            "이재원" to "LEE_JAEWON"



        ),
        "KT" to mapOf(
            "김범석" to "KIM_BEOMSEOK",
            "김성우" to "KIM_SUNGWOO",
            "김준태" to "KIM_JUNTAE",
            "박동원" to "PARK_DONGWON",
            "이주헌" to "LEE_JUHEON",
            "이한림" to "LEE_HANLIM",

            "구본혁" to "KOO_BONHYUK",
            "김민수" to "KIM_MINSOO",
            "김성진" to "KIM_SUNGJIN",
            "김주성" to "KIM_JUSUNG",
            "문보경" to "MOON_BOKYUNG",
            "문정빈" to "MOON_JUNGBIN",
            "손용준" to "SON_YONGJUN",
            "신민재" to "SHIN_MINJAE",
            "오스틴" to "AUSTIN",
            "오지환" to "OH_JIHWAN",
            "이영빈" to "LEE_YOUNGBIN",
            "이태훈" to "LEE_TAEHOON",
            "천성호" to "CHEON_SUNGHO",
            "김대원" to "KIM_DAEWON",

            "김현수" to "KIM_HYUNSOO",
            "김현종" to "KIM_HYUNJONG",
            "문성주" to "MOON_SUNGJOO",
            "박관우" to "PARK_GWANWOO",
            "박해민" to "PARK_HAEMIN",
            "서영준" to "SEO_YOUNGJUN",
            "송찬의" to "SONG_CHANYI",
            "안익훈" to "AN_IKHOON",
            "최승민" to "CHOI_SEUNGMIN",
            "최원영" to "CHOI_WONYOUNG",
            "함창건" to "HAM_CHANGGEON",
            "홍창기" to "HONG_CHANGKI",
            "최명경" to "CHOI_MYUNGKYUNG",
            "이재원" to "LEE_JAEWON"


        ),
        "KIA" to mapOf(
            // --- KIA 타이거즈 ---
            "권다겸" to "KWON_DAGYEOM",
            "김선우" to "KIM_SUNWOO",
            "김태군" to "KIM_TAEGOON",
            "신명승" to "SHIN_MYUNGSEUNG",
            "주효상" to "JOO_HYOSANG",
            "한승택" to "HAN_SEUNGTAEK",
            "한준수" to "HAN_JUNSOO",

            "강민제" to "KANG_MINJE",
            "김규성" to "KIM_GYUSEONG",
            "김도영" to "KIM_DOYOUNG",
            "김선빈" to "KIM_SUNBIN",
            "김재현" to "KIM_JAEHYUN",
            "박민" to "PARK_MIN",
            "박상준" to "PARK_SANGJUN",
            "박찬호" to "PARK_CHANHO",
            "변우혁" to "BYUN_WOOHYUK",
            "서건창" to "SEO_GEONCHANG",
            "염준현" to "YEOM_JUNHYUN",
            "오선우" to "OH_SUNWOO",
            "오정환" to "OH_JUNGHWAN",
            "위즈덤" to "WISDOM",
            "윤도현" to "YOON_DOHYUN",
            "이준범" to "LEE_JUNBEOM",
            "장시현" to "JANG_SIHYEON",
            "정해원" to "JUNG_HAEWON",
            "정현창" to "JUNG_HYUNCHANG",
            "최정용" to "CHOI_JUNGYONG",
            "황대인" to "HWANG_DAEIN",

            "고종욱" to "GO_JONGWOOK",
            "김민수" to "KIM_MINSOO",
            "김석환" to "KIM_SEOKHWAN",
            "김호령" to "KIM_HORYEONG",
            "나성범" to "NA_SUNGBEOM",
            "박재욱" to "PARK_JAEWOOK",
            "박정우" to "PARK_JUNGWOO",
            "박현" to "PARK_HYUN",
            "예진원" to "YE_JINWON",
            "이영재" to "LEE_YOUNGJAE",
            "이창진" to "LEE_CHANGJIN",
            "최형우" to "CHOI_HYUNGWOO",
            "한승연" to "HAN_SEUNGYEON"

        ),
        "삼성" to mapOf(
            // --- 타자 ---
            // --- 삼성 라이온즈 ---
            "박병호" to "PARK_BYUNGHO",
            "강한울" to "KANG_HANUL",
            "적병우" to "JEOK_BYUNGWOO",
            "안주형" to "AN_JOOHYUNG",
            "류시현" to "RYU_SIHYEON",
            "피렐라" to "PIRELLA",
            "이장형" to "LEE_JANGHYUNG",
            "곽민규" to "KWAK_MINGYU",
            "양우현" to "YANG_WOOHYUN",
            "이해승" to "LEE_HAESEUNG",
            "육현석" to "YUK_HYEONSEOK",
            "이제현" to "LEE_JAEHYUN",
            "양훈근" to "YANG_HOONGEUN",
            "김영웅" to "KIM_YOUNGWOONG",
            "박장민" to "PARK_JANGMIN",
            "조민성" to "CHO_MINSEONG",
            "김세형" to "KIM_SEHYEONG",
            "김상준" to "KIM_SANGJUN",
            "강민성" to "KANG_MINSEONG",
            "심재훈" to "SHIM_JAEHOON",
            "차승준" to "CHA_SEUNGJUN",

            "김헌곤" to "KIM_HEONGON",
            "구자욱" to "KOO_JAWOOK",
            "이성규" to "LEE_SUNGKYU",
            "김태훈" to "KIM_TAEHOON",
            "윤정빈" to "YOON_JUNGBIN",
            "김태근" to "KIM_TAEGEUN",
            "홍현빈" to "HONG_HYEONBIN",
            "김성윤" to "KIM_SUNGYOON",
            "박승규" to "PARK_SEUNGKYU",
            "강준서" to "KANG_JUNSEO",
            "김지찬" to "KIM_JICHAN",
            "주하늘" to "JOO_HANEUL",
            "김상민" to "KIM_SANGMIN",
            "함수호" to "HAM_SUHO",
            "이진홍" to "LEE_JINHONG",

            "강민호" to "KANG_MINHO",
            "김민수" to "KIM_MINSOO",
            "김재성" to "KIM_JAESEONG",
            "이병헌" to "LEE_BYUNGHEON",
            "김도환" to "KIM_DOHWAN",
            "차동영" to "CHA_DONGYOUNG",
            "박진우" to "PARK_JINWOO"

        ),
        "두산" to mapOf(
// --- 포수 ---
            // --- 두산 베어스 ---
            "강승호" to "KANG_SEUNGHO",
            "김동준" to "KIM_DONGJUN",
            "김민혁" to "KIM_MINHYUK",
            "김준상" to "KIM_JUNSANG",
            "박계범" to "PARK_GYEBEOM",
            "박준순" to "PARK_JUNSOON",
            "박준영" to "PARK_JUNYOUNG",
            "박지훈" to "PARK_JIHOON",
            "양석환" to "YANG_SEOKHWAN",
            "양찬열" to "YANG_CHANYEOL",
            "여도건" to "YEO_DOGEON",
            "오현진" to "OH_HYUNJIN",
            "이로운" to "LEE_ROWOON",
            "이유찬" to "LEE_YOOCHAN",
            "임종성" to "LIM_JONGSUNG",
            "김기연" to "KIM_GIYEON",

            "류현준" to "RYU_HYUNJUN",
            "박민준" to "PARK_MINJUN",
            "박성재" to "PARK_SUNGJAE",
            "양의지" to "YANG_EUIJI",
            "정승진" to "JUNG_SEUNGJIN",
            "장승현" to "JANG_SEUNGHYUN",
            "전준우" to "JEON_JUNWOO",
            "김대한" to "KIM_DAEHAN",
            "김민석" to "KIM_MINSEOK",
            "김태헌" to "KIM_TAEHEON",
            "김재환" to "KIM_JAEHWAN",
            "전다민" to "JEON_DAMIN",
            "정수빈" to "JUNG_SOOBIN",
            "조수행" to "CHO_SUHANG",

            "추재현" to "CHOO_JAEHYUN",
            "케이브" to "CAVE",
            "홍성호" to "HONG_SUNGHO"



        ),
        "SSG" to mapOf(
// --- 포수 ---
            // --- SSG 랜더스 ---
            "김규민" to "KIM_GYUMIN",
            "김민식" to "KIM_MINSIK",
            "신범수" to "SHIN_BEOMSOO",
            "이율예" to "LEE_YULYE",
            "이지영" to "LEE_JIYOUNG",
            "조형우" to "CHO_HYEONGWOO",

            "고명준" to "GO_MYUNGJOON",
            "김성민" to "KIM_SEONGMIN",
            "김성현" to "KIM_SEONGHYUN",
            "김수윤" to "KIM_SUYOON",
            "김찬형" to "KIM_CHANHYUNG",
            "김태윤" to "KIM_TAEYOON",
            "박성한" to "PARK_SEONGHAN",
            "박지환" to "PARK_JIHWAN",
            "석정우" to "SEOK_JUNGWOO",
            "안상현" to "AN_SANGHYUN",
            "장현진" to "JANG_HYEONJIN",
            "정준재" to "JUNG_JUNJAE",
            "최윤석" to "CHOI_YOONSEOK",
            "최정" to "CHOI_JEONG",
            "최준우" to "CHOI_JUNWOO",
            "현원회" to "HYUN_WONHOE",
            "홍대인" to "HONG_DAEIN",

            "기예르모 에레디아" to "GUILLERMO_HEREDIA",
            "김성욱" to "KIM_SUNGWOOK",
            "김정민" to "KIM_JUNGMIN",
            "김창평" to "KIM_CHANGPYEONG",
            "류효승" to "RYU_HYOSEUNG",
            "박정빈" to "PARK_JUNGBIN",
            "오태곤" to "OH_TAEGON",
            "이승민" to "LEE_SEUNGMIN",
            "이원준" to "LEE_WONJUN",
            "이정범" to "LEE_JUNGBEOM",
            "임근우" to "LIM_GEUNWOO",
            "채현우" to "CHAE_HYEONWOO",
            "최지훈" to "CHOI_JIHOON",
            "하재훈" to "HA_JAEHOON",
            "한유섬" to "HAN_YOOSEOM"




        ),
        "롯데" to mapOf(
// --- 포수 ---
            // --- 롯데 자이언츠 ---
            "강승구" to "KANG_SEUNGKOO",
            "박건우" to "PARK_GUNWOO",
            "박재엽" to "PARK_JAEYEOB",
            "손성빈" to "SON_SEONGBIN",
            "엄장윤" to "EOM_JANGYOON",
            "유강남" to "YOO_GANGNAM",
            "정보근" to "JUNG_BOGEUN",

            "강성우" to "KANG_SUNGWOO",
            "고승민" to "GO_SEUNGMIN",
            "김동규" to "KIM_DONGGYU",
            "김민성" to "KIM_MINSUNG",
            "김세민" to "KIM_SEMIN",
            "노진혁" to "NO_JINHYUK",
            "박승욱" to "PARK_SEUNGWOOK",
            "박지훈" to "PARK_JIHOON",
            "박창형" to "PARK_CHANGHYUNG",
            "배인혁" to "BAE_INHYUK",
            "손호영" to "SON_HOYOUNG",
            "신윤후" to "SHIN_YUNHOO",
            "유태웅" to "YOO_TAEWOONG",
            "이주찬" to "LEE_JOOCHAN",
            "이태경" to "LEE_TAEKYUNG",
            "이호준" to "LEE_HOJUN",
            "전민재" to "JEON_MINJAE",
            "정훈" to "JUNG_HOON",
            "최민규" to "CHOI_MINGYU",
            "최홍" to "CHOI_HONG",
            "한태양" to "HAN_TAEYANG",

            "김대현" to "KIM_DAEHYUN",
            "김동혁" to "KIM_DONGHYUK",
            "김동현" to "KIM_DONGHYUN",
            "박건" to "PARK_GEON",
            "빅터 레예스" to "VICTOR_REYES",
            "윤동희" to "YOON_DONGHEE",
            "윤수녕" to "YOON_SOONYUNG",
            "이상화" to "LEE_SANGHWA",
            "이인한" to "LEE_INHAN",
            "장두성" to "JANG_DOOSEONG",
            "전준우" to "JEON_JUNWOO",
            "조세진" to "CHO_SEJIN",
            "한승현" to "HAN_SEUNGHYUN",
            "황성빈" to "HWANG_SEONGBIN"



        ),
        "한화" to mapOf(
// --- 포수 ---
            // --- 한화 이글스 ---
            "허광회" to "HEO_GWANGHOE",
            "최재훈" to "CHOI_JAEHOON",
            "이재원" to "LEE_JAEWON",
            "장규현" to "JANG_GYUHYEON",
            "박상언" to "PARK_SANGEON",
            "허인서" to "HEO_INSEO",
            "한지윤" to "HAN_JIYOON",

            "심우준" to "SHIM_WOOJOON",
            "안치홍" to "AN_CHIHOONG",
            "조한민" to "CHO_HANMIN",
            "한경빈" to "HAN_GYEONGBIN",
            "이도윤" to "LEE_DOYOON",
            "노시환" to "NO_SIHWAN",
            "하주석" to "HA_JOOSEOK",
            "권광민" to "KWON_GWANGMIN",
            "채은성" to "CHAE_EUNSUNG",
            "김인환" to "KIM_INHWAN",
            "문현빈" to "MOON_HYEONBIN",
            "김건" to "KIM_GUN",
            "이승현" to "LEE_SEUNGHYUN",
            "박정현" to "PARK_JUNGHYUN",
            "정민규" to "JUNG_MINGYU",
            "황영묵" to "HWANG_YEONGMOOK",
            "배승수" to "BAE_SEUNGSOO",
            "최원준" to "CHOI_WONJUN",
            "이지성" to "LEE_JISEONG",
            "노석진" to "NO_SEOKJIN",

            "리베라토" to "LIBERATO",
            "이상혁" to "LEE_SANGHYUK",
            "이진영" to "LEE_JINYOUNG",
            "임종찬" to "LIM_JONGCHAN",
            "김태연" to "KIM_TAEYEON",
            "손아섭" to "SON_ASEOP",
            "유로결" to "YOO_ROGYUL",
            "최인호" to "CHOI_INHO",
            "이원석" to "LEE_WONSEOK",
            "이민재" to "LEE_MINJAE",
            "최준서" to "CHOI_JUNSEO",
            "유민" to "YOO_MIN",
            "김해찬" to "KIM_HAECHAN"



        ),
        "NC" to mapOf(
            // --- 포수 ---
            // --- NC 다이노스 ---
            "안중열" to "AN_JUNGYEOL",
            "박세혁" to "PARK_SEHYUK",
            "김형준" to "KIM_HYEONGJUN",
            "김정호" to "KIM_JUNGHO",
            "박성재" to "PARK_SEONGJAE",
            "김동헌" to "KIM_DONGHEON",
            "김태호" to "KIM_TAEHO",
            "신민우" to "SHIN_MINWOO",

            "박민우" to "PARK_MINWOO",
            "홍종표" to "HONG_JONGPYO",
            "서호철" to "SEO_HOCHEOL",
            "오태양" to "OH_TAEYANG",
            "김주원" to "KIM_JUWON",
            "김세훈" to "KIM_SEHOON",
            "최정원" to "CHOI_JUNGWON",
            "도태훈" to "DO_TAEHOON",
            "데이비슨" to "DAVIDSON",
            "오영수" to "OH_YOUNGSOO",
            "한재환" to "HAN_JAEHWAN",
            "안인산" to "AN_INSAN",
            "김휘집" to "KIM_HWEEJIP",
            "김한별" to "KIM_HANBYEOL",
            "장창훈" to "JANG_CHANGHOON",
            "박인우" to "PARK_INWOO",
            "박주찬" to "PARK_JOOCHAN",
            "신성호" to "SHIN_SEONGHO",
            "이한" to "LEE_HAN",
            "유재현" to "YOO_JAEHYUN",
            "조준원" to "CHO_JUNWON",
            "최보성" to "CHOI_BOSEONG",

            "송승환" to "SONG_SEUNGHWAN",
            "천재환" to "CHEON_JAEHWAN",
            "최원준" to "CHOI_WONJUN",
            "한석현" to "HAN_SEOKHYUN",
            "권희동" to "KWON_HEEDONG",
            "박건우" to "PARK_GUNWOO",
            "박영빈" to "PARK_YOUNGBIN",
            "박시원" to "PARK_SIWON",
            "이우성" to "LEE_WOOSEONG",
            "고승완" to "GO_SEUNGWAN",
            "김범준" to "KIM_BUMJUN",
            "오장환" to "OH_JANGHWAN",
            "양가운솔" to "YANG_GAUNSOL",
            "조창연" to "CHO_CHANGYEON"

        )
        ,
        "키움" to mapOf(
            // --- 포수 ---
            // --- 키움 히어로즈 ---
            "김건희" to "KIM_GUNHEE",
            "김동헌" to "KIM_DONGHEON",
            "김재현" to "KIM_JAEHYUN",
            "김지성" to "KIM_JISEONG",
            "박성빈" to "PARK_SEONGBIN",
            "박준형" to "PARK_JUNHYUNG",
            "김리안" to "KIM_LIAN",

            "강진성" to "KANG_JINSEONG",
            "고영우" to "GO_YOUNGWOO",
            "권혁빈" to "KWON_HYUKBIN",
            "김병휘" to "KIM_BYUNGHWI",
            "김웅빈" to "KIM_WOONGBIN",
            "김태진" to "KIM_TAEJIN",
            "서유신" to "SEO_YOOSHIN",
            "송성문" to "SONG_SEONGMOON",
            "송지후" to "SONG_JIHOO",
            "심휘윤" to "SIM_HWUYUN",
            "양현종" to "YANG_HYUNJONG",
            "어준서" to "EO_JUNSEO",
            "여동욱" to "YEO_DONGWOOK",
            "염승원" to "YEOM_SEUNGWON",
            "오선진" to "OH_SEONJIN",
            "이명기" to "LEE_MYUNGKI",
            "이승원" to "LEE_SEUNGWON",
            "이원석" to "LEE_WONSEOK",
            "이재상" to "LEE_JAESANG",
            "이주형" to "LEE_JOOHYUNG",
            "전태현" to "JEON_TAEHYUN",
            "최주환" to "CHOI_JOOHWAN",
            "원성준" to "WON_SEONGJUN",

            "김동엽" to "KIM_DONGYEOP",
            "박수종" to "PARK_SUJONG",
            "박주홍" to "PARK_JUHONG",
            "박채울" to "PARK_CHAEWOO",
            "변상권" to "BYUN_SANGGWON",
            "이용규" to "LEE_YONGGYU",
            "이주형" to "LEE_JOOHYUNG",
            "이형종" to "LEE_HYEONGJONG",
            "임병욱" to "LIM_BYUNGWOOK",
            "임지열" to "LIM_JIYEOL",
            "장재영" to "JANG_JAEYOUNG",
            "주성원" to "JOO_SEONGWON",
            "카디네스" to "CARDENAS",
            "스톤 개랫" to "STONE_GARRETT"

        )
    )

    private lateinit var layout: LinearLayout

    @SuppressLint("MissingPermission")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_connected)
        layout = findViewById(R.id.layoutContainer)

        showTeamList()  // 처음엔 구단 목록 표시
    }

    // ✅ 구단 목록 표시
    private fun showTeamList() {
        layout.removeAllViews()

        val title = TextView(this).apply {
            text = "구단 선택"
            textSize = 22f
            setPadding(0, 0, 0, 16)
        }
        layout.addView(title)

        for (team in teamPlayers.keys) {
            val teamButton = Button(this).apply {
                text = team
                textSize = 18f
            }
            teamButton.setOnClickListener {
                showPlayersForTeam(team)
            }
            layout.addView(teamButton)
        }
        // ====== 🔽 방향 버튼 추가 영역 ======
        val buttonLayout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, 60, 0, 0)
            gravity = android.view.Gravity.CENTER_HORIZONTAL
        }

        // 🔁 버튼을 누르고 있는 동안 반복 전송 함수
        fun setRepeatSend(button: Button, message: String) {
            var timer: Timer? = null
            button.setOnTouchListener { _, event ->
                when (event.action) {
                    android.view.MotionEvent.ACTION_DOWN -> {
                        timer = Timer()
                        timer?.schedule(object : TimerTask() {
                            override fun run() {
                                runOnUiThread {
                                    sendMessageToPi(message)
                                }
                            }
                        }, 0, 50) // 100ms마다 전송
                    }
                    android.view.MotionEvent.ACTION_UP,
                    android.view.MotionEvent.ACTION_CANCEL -> {
                        timer?.cancel()
                        timer = null
                    }
                }
                true
            }
        }

        // ✅ 버튼 크기 통일
        val buttonWidth = 250
        val buttonHeight = 180
        val buttonParams = LinearLayout.LayoutParams(buttonWidth, buttonHeight)

        // 🔼 위쪽 화살표 버튼
        val upButton = Button(this).apply {
            text = "▲"
            textSize = 26f
            layoutParams = buttonParams
        }
        setRepeatSend(upButton, "front")

        // ◀ ▶ 버튼
        val leftRightLayout = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = android.view.Gravity.CENTER
        }

        val leftButton = Button(this).apply {
            text = "◀"
            textSize = 26f
            layoutParams = buttonParams
        }
        setRepeatSend(leftButton, "left")

        val rightButton = Button(this).apply {
            text = "▶"
            textSize = 26f
            layoutParams = buttonParams
        }
        setRepeatSend(rightButton, "right")

        leftRightLayout.addView(leftButton)
        leftRightLayout.addView(Space(this).apply { layoutParams = LinearLayout.LayoutParams(60, 0) })
        leftRightLayout.addView(rightButton)

        // 버튼 순서대로 배치
        buttonLayout.addView(upButton)
        buttonLayout.addView(leftRightLayout)
        layout.addView(buttonLayout)
    }





    // ✅ 선수 목록 표시
    @SuppressLint("MissingPermission")
    private fun showPlayersForTeam(team: String) {
        layout.removeAllViews()

        val title = TextView(this).apply {
            text = "$team 선수 목록"
            textSize = 20f
            setPadding(0, 20, 0, 10)
        }
        layout.addView(title)

        val players = teamPlayers[team] ?: emptyMap()

        for ((korName, engName) in players) {
            val playerButton = Button(this).apply {
                text = korName
                textSize = 16f
            }
            playerButton.setOnClickListener {
                sendMessageToPi(engName)   // 영어 이름 전송
            }
            layout.addView(playerButton)
        }

        val backButton = Button(this).apply {
            text = "◀ 구단 목록으로"
            textSize = 16f
        }
        backButton.setOnClickListener {
            showTeamList()
        }
        layout.addView(backButton)
    }


    // ✅ BLE 전송 함수
    @SuppressLint("MissingPermission")
    private fun sendMessageToPi(message: String) {
        val service = gatt.getService(SERVICE_UUID)
        val characteristic = service?.getCharacteristic(CHAR_UUID)

        if (service == null || characteristic == null) {
            Toast.makeText(this, "BLE 서비스 또는 특성 없음", Toast.LENGTH_SHORT).show()
            return
        }

        characteristic.value = message.toByteArray()
        characteristic.writeType = BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
        val success = gatt.writeCharacteristic(characteristic)

        val toastText = if (success) "[$message] 전송됨" else "전송 실패"
        Toast.makeText(this, toastText, Toast.LENGTH_SHORT).show()
    }
}
