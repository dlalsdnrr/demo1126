package com.example.baseball

import android.annotation.SuppressLint
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCharacteristic
import android.os.Bundle
import android.widget.*
import androidx.activity.ComponentActivity
import com.example.baseball.R
import java.util.*
import android.view.View
import android.graphics.Color
import android.graphics.BitmapFactory


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
            "강백호" to "KANG_BAEKHO",
            "강현우" to "KANG_HYEONWOO",
            "김민석" to "KIM_MINSEOK",
            "장성우" to "JANG_SEONGWOO",
            "조대현" to "JO_DAEHYEON",
            "강민성" to "KANG_MINSEONG",

            "권동진" to "KWON_DONGJIN",
            "김상수" to "KIM_SANGSOO",
            "문상철" to "MOON_SANCHEOL",
            "박민석" to "PARK_MINSEOK",
            "오서진" to "OH_SEOJIN",
            "오윤석" to "OH_YOONSEOK",
            "오재일" to "OH_JAEIL",
            "윤준혁" to "YOON_JUNHYEOK",
            "이호연" to "LEE_HOYEON",
            "장준원" to "JANG_JUNWON",
            "허경민" to "HEO_GYUNGMIN",
            "황재균" to "HWANG_JAEGEUN",
            "김건형" to "KIM_GUNGYUNG",
            "김민혁" to "KIM_MINHYEOK",

            "김병준" to "KIM_BYUNGJUN",
            "박민석" to "PARK_MINSEOK",
            "배정대" to "BAE_JUNGDAE",
            "송민섭" to "SONG_MINSUB",
            "스티븐슨" to "STEVENSEN",
            "안치영" to "AHN_CHIYEONG",
            "안현민" to "AHN_HYEONMIN",
            "유준규" to "YOO_JUNGUE",
            "이정훈" to "LEE_JEONGHUN",
            "장진혁" to "JANG_JINHYUK",
            "최성민" to "CHOI_SEONGMIN"


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
            "박정우" to "PARK_JUNGWOO",
            "박현" to "PARK_HYUN",
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
            "전병우" to "JEON_BYUNGWOO",
            "안주형" to "AN_JOOHYUNG",
            "류지혁" to "RYU_JIHYEOK",
            "디아즈" to "DIAZ",
            "이창용" to "LEE_CHANGYONG",
            "공민규" to "GONG_MINGYU",
            "양우현" to "YANG_WOOHYUN",
            "이해승" to "LEE_HAESEUNG",
            "오현석" to "OH_HYEONSEOK",
            "이재현" to "LEE_JAEHYUN",
            "양도근" to "YANG_DOGEUN",
            "김영웅" to "KIM_YOUNGWOONG",
            "박장민" to "PARK_JANGMIN",
            "조민성" to "CHO_MINSEONG",
            "김재형" to "KIM_JAEYEONG",
            "김상준" to "KIM_SANGJUN",
            "강민성" to "KANG_MINSEONG",
            "심재훈" to "SHIM_JAEHOON",
            "차승준" to "CHA_SEUNGJUN",

            "김헌곤" to "KIM_HEONGON",
            "구자욱" to "KOO_JAWOOK",
            "이성규" to "LEE_SUNGKYU",
            "김태훈" to "KIM_TAEHOON",
            "김태근" to "KIM_TAEGEUN",
            "홍현빈" to "HONG_HYEONBIN",
            "김성윤" to "KIM_SUNGYOON",
            "박승규" to "PARK_SEUNGKYU",
            "강준서" to "KANG_JUNSEO",
            "김지찬" to "KIM_JICHAN",
            "주한울" to "JOO_HANOOL",
            "김상민" to "KIM_SANGMIN",
            "함수호" to "HAM_SUHO",
            "이진용" to "LEE_JINYONG",

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
            "여동건" to "YEO_DONGEON",
            "오명진" to "OH_MYUNGJIN",
            "이선우" to "LEE_SEONWOO",
            "이유찬" to "LEE_YOOCHAN",
            "임종성" to "LIM_JONGSUNG",
            "김기연" to "KIM_GIYEON",

            "류현준" to "RYU_HYUNJUN",
            "박민준" to "PARK_MINJUN",
            "박성재" to "PARK_SUNGJAE",
            "양의지" to "YANG_EUIJI",
            "장승현" to "JANG_SEUNGHYUN",
            "김대한" to "KIM_DAEHAN",
            "김민석" to "KIM_MINSEOK",
            "김인태" to "KIM_INTAE",
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
            "박찬형" to "PARK_CHANHYUNG",
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
            "최항" to "CHOI_HANG",
            "한태양" to "HAN_TAEYANG",

            "김대현" to "KIM_DAEHYUN",
            "김동혁" to "KIM_DONGHYUK",
            "김동현" to "KIM_DONGHYUN",
            "박건" to "PARK_GEON",
            "빅터 레이예스" to "VICTOR_REYES",
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
            "허관회" to "HEO_GWANHOE",
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
            "김동현" to "KIM_DONGHEON",
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
            "조효원" to "CHO_JUNWON",

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
            "오장한" to "OH_JANGHWAN",
            "양가온솔" to "YANG_GAUNSOL",
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
    // ✅ 구단 목록 표시
    private fun showTeamList() {
        layout.removeAllViews()

        val title = TextView(this).apply {
            text = "응원하실 구단을 선택해주세요"
            textSize = 22f
            setPadding(0, 0, 0, 16)
        }
        layout.addView(title)

        // ✅ 각 구단별 버튼 생성 (2열 배치)
        val teams = teamPlayers.keys.toList()
        for (i in teams.indices step 2) {
            val rowLayout = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = android.view.Gravity.CENTER
            }

            val buttonParams = LinearLayout.LayoutParams(0, 220, 1f).apply {
                setMargins(30, 20, 30, 20)
            }

            fun createTeamButton(teamName: String): LinearLayout {
                val teamLayout = LinearLayout(this).apply {
                    orientation = LinearLayout.HORIZONTAL
                    gravity = android.view.Gravity.CENTER_VERTICAL

                    // ✅ 구단별 색상
                    val colorHex = when (teamName) {
                        "LG" -> "#C30452"
                        "KT" -> "#000000"
                        "KIA" -> "#E61E2B"
                        "삼성" -> "#074CA1"
                        "두산" -> "#131230"
                        "SSG" -> "#E71E26"
                        "롯데" -> "#002955"
                        "한화" -> "#F15A22"
                        "NC" -> "#1D467C"
                        "키움" -> "#830000"
                        else -> "#808080"
                    }

                    // ✅ 모서리 둥근 배경 drawable 생성
                    val backgroundDrawable = android.graphics.drawable.GradientDrawable().apply {
                        setColor(android.graphics.Color.parseColor(colorHex)) // 배경색
                        cornerRadius = 40f  // ✅ 모서리 둥근 정도(px) — 숫자 키우면 더 둥글어짐
                    }

                    background = backgroundDrawable  // ✅ 배경으로 설정

                    layoutParams = buttonParams
                    setPadding(20, 10, 20, 10)
                    elevation = 8f  // 살짝 입체감(그림자 효과)
                }

                // ✅ 구단 로고
                val imageView = ImageView(this).apply {
                    setImageResource(
                        when (teamName) {
                            "LG" -> R.drawable.lg
                            "KT" -> R.drawable.kt
                            "KIA" -> R.drawable.kia
                            "삼성" -> R.drawable.samsung
                            "두산" -> R.drawable.doosan
                            "SSG" -> R.drawable.ssg
                            "롯데" -> R.drawable.lotte
                            "한화" -> R.drawable.hanwha
                            "NC" -> R.drawable.nc
                            "키움" -> R.drawable.kiwoom
                            else -> 0
                        }
                    )
                    layoutParams = LinearLayout.LayoutParams(140, 140).apply {
                        rightMargin = 20
                    }
                }

                // ✅ 구단 이름
                val textView = TextView(this).apply {
                    text = teamName
                    textSize = 20f
                    setTextColor(android.graphics.Color.WHITE)
                }

                teamLayout.addView(imageView)
                teamLayout.addView(textView)

                teamLayout.setOnClickListener {
                    showCheerOptionsForTeam(teamName)
                }


                return teamLayout
            }



            val team1 = teams[i]
            rowLayout.addView(createTeamButton(team1))

            if (i + 1 < teams.size) {
                val team2 = teams[i + 1]
                rowLayout.addView(createTeamButton(team2))
            }

            layout.addView(rowLayout)
        }



        // ✅ 구단 버튼들과 조종 버튼 사이에 회색 구분선 + "로봇 이동" 텍스트 추가

// 1️⃣ 먼저 회색 구분선
        val divider = View(this).apply {
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                3 // 선 두께(px)
            ).apply {
                topMargin = 40
                bottomMargin = 20
                leftMargin = 80
                rightMargin = 80
            }
            setBackgroundColor(Color.parseColor("#CCCCCC")) // 연회색
        }
        layout.addView(divider)

// 2️⃣ 그 아래 "로봇 이동" 텍스트
        val moveTitle = TextView(this).apply {
            text = "로봇 이동"
            textSize = 22f
            setTypeface(null, android.graphics.Typeface.BOLD)
            setTextColor(Color.parseColor("#333333"))
            gravity = android.view.Gravity.CENTER

            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply {
                topMargin = 10
                bottomMargin = 30
            }
        }
        layout.addView(moveTitle)




        // ====== 🔽 방향 버튼 추가 영역 ======
        // ====== 🔽 방향 버튼 추가 영역 ======
        val buttonLayout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, 60, 0, 0)
            gravity = android.view.Gravity.CENTER_HORIZONTAL
        }

        // ✅ 공통 버튼 배경 (모서리 둥근 스타일)
        fun createRoundedBackground(color: Int): android.graphics.drawable.GradientDrawable {
            return android.graphics.drawable.GradientDrawable().apply {
                setColor(color)           // 배경색
                cornerRadius = 60f        // ✅ 모서리 둥근 정도(px)
                setStroke(4, Color.DKGRAY) // 테두리선 (진한 회색)
            }
        }

        // ✅ 버튼 반복 전송 설정 (기존 코드 그대로 유지)
        fun setRepeatSend(button: Button, message: String) {
            var timer: Timer? = null
            button.setOnTouchListener { _, event ->
                when (event.action) {
                    android.view.MotionEvent.ACTION_DOWN -> {
                        timer = Timer()
                        timer?.schedule(object : TimerTask() {
                            override fun run() {
                                runOnUiThread { sendMessageToPi(message) }
                            }
                        }, 0, 50)
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

        val buttonWidth = 250
        val buttonHeight = 180
        val buttonParams = LinearLayout.LayoutParams(buttonWidth, buttonHeight).apply {
            setMargins(20, 10, 20, 10)
        }

// ✅ 위쪽(앞으로 이동) 버튼
        val upButton = Button(this).apply {
            text = "▲"
            textSize = 26f
            layoutParams = buttonParams
            background = createRoundedBackground(Color.parseColor("#4CAF50")) // 초록색
            setTextColor(Color.WHITE)
        }
        setRepeatSend(upButton, "front")

// ✅ 좌우 버튼 레이아웃
        val leftRightLayout = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = android.view.Gravity.CENTER
        }

        val leftButton = Button(this).apply {
            text = "◀"
            textSize = 26f
            layoutParams = buttonParams
            background = createRoundedBackground(Color.parseColor("#2196F3")) // 파란색
            setTextColor(Color.WHITE)
        }
        setRepeatSend(leftButton, "left")

        val rightButton = Button(this).apply {
            text = "▶"
            textSize = 26f
            layoutParams = buttonParams
            background = createRoundedBackground(Color.parseColor("#2196F3")) // 파란색
            setTextColor(Color.WHITE)
        }
        setRepeatSend(rightButton, "right")

// 좌우 버튼 간 여백 추가
        leftRightLayout.addView(leftButton)
        leftRightLayout.addView(Space(this).apply {
            layoutParams = LinearLayout.LayoutParams(60, 0)
        })
        leftRightLayout.addView(rightButton)

// 전체 배치
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
            textSize = 22f
            setPadding(0, 20, 0, 10)
            gravity = android.view.Gravity.CENTER
        }
        layout.addView(title)

        val players = teamPlayers[team] ?: emptyMap()
        val playerList = players.toList()

        // ✅ 2열 구조 표시
        for (i in playerList.indices step 2) {
            val rowLayout = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = android.view.Gravity.CENTER
            }

            val buttonParams = LinearLayout.LayoutParams(0, 400, 1f).apply {
                setMargins(20, 20, 20, 20)
            }

            fun createPlayerCard(korName: String, engName: String): LinearLayout {
                val container = LinearLayout(this).apply {
                    orientation = LinearLayout.VERTICAL
                    gravity = android.view.Gravity.CENTER
                    layoutParams = buttonParams
                    background = android.graphics.drawable.GradientDrawable().apply {
                        setColor(Color.WHITE)
                        cornerRadius = 40f
                        setStroke(4, Color.LTGRAY)
                    }
                    setPadding(10, 10, 10, 10)
                    elevation = 8f
                }

                // ✅ team 이름을 소문자로 바꿔 assets 경로 자동 설정
                val teamFolder = team.lowercase(Locale.getDefault())

                val imageView = ImageView(this).apply {
                    layoutParams = LinearLayout.LayoutParams(
                        LinearLayout.LayoutParams.MATCH_PARENT, 300
                    )
                    scaleType = ImageView.ScaleType.CENTER_CROP
                    try {
                        val inputStream = try {
                            assets.open("players/$teamFolder/${korName}.png")
                        } catch (e1: Exception) {
                            try {
                                assets.open("players/$teamFolder/${korName}.jpg")
                            } catch (e2: Exception) {
                                try {
                                    assets.open("players/$teamFolder/${korName}.jpeg")
                                } catch (e3: Exception) {
                                    assets.open("players/$teamFolder/${korName}.webp")
                                }
                            }
                        }
                        val bitmap = BitmapFactory.decodeStream(inputStream)
                        setImageBitmap(bitmap)
                        inputStream.close()
                    } catch (e: Exception) {
                        setBackgroundColor(Color.LTGRAY)
                    }
                }

                val nameText = TextView(this).apply {
                    text = korName
                    textSize = 18f
                    gravity = android.view.Gravity.CENTER
                    setTextColor(Color.BLACK)
                }

                container.addView(imageView)
                container.addView(nameText)

                container.setOnClickListener {
                    sendMessageToPi(engName)
                }

                return container
            }

            val (kor1, eng1) = playerList[i]
            rowLayout.addView(createPlayerCard(kor1, eng1))

            if (i + 1 < playerList.size) {
                val (kor2, eng2) = playerList[i + 1]
                rowLayout.addView(createPlayerCard(kor2, eng2))
            }

            layout.addView(rowLayout)
        }

        val backButton = Button(this).apply {
            text = "◀ 응원 메뉴로"
            textSize = 18f
        }
        backButton.setOnClickListener {
            showCheerOptionsForTeam(team)
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

    @SuppressLint("MissingPermission")
    private fun showCheerOptionsForTeam(team: String) {
        layout.removeAllViews()

        val frameLayout = FrameLayout(this)
        layout.addView(frameLayout)

        // ⚾ 배경 이미지 (야구장)
        val backgroundImage = ImageView(this).apply {
            setImageResource(R.drawable.baseball_field)
            scaleType = ImageView.ScaleType.FIT_CENTER
            alpha = 1.0f
            layoutParams = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.WRAP_CONTENT
            ).apply {
                topMargin = 80
            }
        }
        frameLayout.addView(backgroundImage)

        // ⚾ 구단별 로고 오버레이 (✅ 추가된 부분)
        val teamOverlay = ImageView(this).apply {
            setImageResource(
                when (team) {
                    "LG" -> R.drawable.lg
                    "KT" -> R.drawable.kt
                    "KIA" -> R.drawable.kia
                    "삼성" -> R.drawable.samsung
                    "두산" -> R.drawable.doosan
                    "SSG" -> R.drawable.ssg
                    "롯데" -> R.drawable.lotte
                    "한화" -> R.drawable.hanwha
                    "NC" -> R.drawable.nc
                    "키움" -> R.drawable.kiwoom
                    else -> R.drawable.kbo_logo
                }
            )
            layoutParams = FrameLayout.LayoutParams(
                200, 200
            ).apply {
                gravity = android.view.Gravity.TOP or android.view.Gravity.CENTER_HORIZONTAL
                topMargin = 100
            }
            scaleType = ImageView.ScaleType.FIT_CENTER
            alpha = 1.0f
        }
        frameLayout.addView(teamOverlay)

        // ⚾ 버튼 등 나머지 기존 코드 계속 ↓↓↓


        // ✅ 홈런 버튼 (전광판 위치)
        val homeRunBtn = Button(this).apply {
            text = "홈런"
            textSize = 16f
            background = roundedButton(Color.parseColor("#D32F2F"))
            setTextColor(Color.WHITE)
            layoutParams = FrameLayout.LayoutParams(220, 130).apply {
                gravity = android.view.Gravity.TOP or android.view.Gravity.CENTER_HORIZONTAL
                topMargin = 500   // 전광판 쪽으로
            }
            setOnClickListener { sendMessageToPi("HOMERUN") }
        }
        frameLayout.addView(homeRunBtn)

        // ✅ 1루타 버튼
        val hit1Btn = Button(this).apply {
            text = "1루타"
            textSize = 15f
            background = roundedButton(Color.parseColor("#1976D2"))
            setTextColor(Color.WHITE)
            layoutParams = FrameLayout.LayoutParams(180, 120).apply {
                gravity = android.view.Gravity.CENTER
                leftMargin = 200  // 오른쪽으로
                topMargin = 150   // 중앙보다 아래쪽
            }
            setOnClickListener { sendMessageToPi("HIT1") }
        }
        frameLayout.addView(hit1Btn)

        // ✅ 2루타 버튼
        val hit2Btn = Button(this).apply {
            text = "2루타"
            textSize = 15f
            background = roundedButton(Color.parseColor("#1976D2"))
            setTextColor(Color.WHITE)
            layoutParams = FrameLayout.LayoutParams(180, 120).apply {
                gravity = android.view.Gravity.CENTER
                topMargin = 80   // 위쪽 (2루 근처)
            }
            setOnClickListener { sendMessageToPi("HIT2") }
        }
        frameLayout.addView(hit2Btn)

        // ✅ 3루타 버튼
        val hit3Btn = Button(this).apply {
            text = "3루타"
            textSize = 15f
            background = roundedButton(Color.parseColor("#1976D2"))
            setTextColor(Color.WHITE)
            layoutParams = FrameLayout.LayoutParams(180, 120).apply {
                gravity = android.view.Gravity.CENTER
                rightMargin = 200  // 왼쪽으로
                topMargin = 150
            }
            setOnClickListener { sendMessageToPi("HIT3") }
        }
        frameLayout.addView(hit3Btn)

        // ✅ 아웃 버튼 (아래쪽)
        val outBtn = Button(this).apply {
            text = "아웃"
            textSize = 16f
            background = roundedButton(Color.parseColor("#F57C00"))
            setTextColor(Color.WHITE)
            layoutParams = FrameLayout.LayoutParams(250, 130).apply {
                gravity = android.view.Gravity.BOTTOM or android.view.Gravity.CENTER_HORIZONTAL
                bottomMargin = 280
            }
            setOnClickListener {
                // 팀 이름을 영어 대문자로 변환 후 조합 (ex: KT → KTOUT)
                val teamCode = when (team) {
                    "LG" -> "LG"
                    "KT" -> "KT"
                    "KIA" -> "KIA"
                    "삼성" -> "SS"
                    "두산" -> "DS"
                    "SSG" -> "SSG"
                    "롯데" -> "LT"
                    "한화" -> "HH"
                    "NC" -> "NC"
                    "키움" -> "KW"
                    else -> "TEAM"
                }
                sendMessageToPi("${teamCode}OUT")
            }

        }
        frameLayout.addView(outBtn)

        // ✅ 선수 응원 버튼 (가장 아래)
        val playerBtn = Button(this).apply {
            text = "선수 응원"
            textSize = 18f
            background = roundedButton(Color.parseColor("#388E3C"))
            setTextColor(Color.WHITE)
            layoutParams = FrameLayout.LayoutParams(350, 150).apply {
                gravity = android.view.Gravity.BOTTOM or android.view.Gravity.CENTER_HORIZONTAL
                bottomMargin = 100
            }
            setOnClickListener { showPlayersForTeam(team) }
        }
        frameLayout.addView(playerBtn)

        // ✅ 뒤로가기 버튼
        val backBtn = Button(this).apply {
            text = "◀ 구단 목록으로"
            textSize = 16f
            layoutParams = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.WRAP_CONTENT,
                FrameLayout.LayoutParams.WRAP_CONTENT
            ).apply {
                gravity = android.view.Gravity.TOP or android.view.Gravity.START
                leftMargin = 40
                topMargin = 40
            }
            setOnClickListener { showTeamList() }
        }
        frameLayout.addView(backBtn)
    }

    // ✅ 둥근 버튼 스타일 재사용 함수
    private fun roundedButton(color: Int): android.graphics.drawable.GradientDrawable {
        return android.graphics.drawable.GradientDrawable().apply {
            setColor(color)
            cornerRadius = 50f
        }
    }



}

