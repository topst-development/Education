#include "stdint.h"
#include "enlight_network.h"
#include <stdlib.h>
#include <string.h>
#ifdef __i386__
#   include <stdio.h>
#   define post_process_log(...) do {printf(__VA_ARGS__);} while(0)
#else
#   define post_process_log(...) do {_printf(__VA_ARGS__);} while(0)
#endif

extern void custom_postproc_init();

typedef struct {
    float loc[72]; // 각 lane 포인트의 위치 정보
} custom_lane_t;

/** @brief Run custom post-processing
 *
 *      Lane 정보 추출 및 저장
 *      
 *
 *  @param net_inst         instance Network instance.
 *  @param output_base      output tensor buffer base
 *  @param num_input        입력 데이터 개수
 *  @param custom_loc       후처리 결과를 저장할 custom_lane_t 구조체
 *
 *  @return Return number of output
 */
int run_post_process(
    void *net_inst,        // 네트워크 인스턴스
    void *output_base,     // 출력 데이터 베이스
    int num_input,         // 입력 데이터 개수
    custom_lane_t *custom_loc // custom_lane_t 구조체 추가
) {
    enlight_network_t *inst;
    enlight_custom_postproc_t *custom_param;
    int result;
    int i, num_output;
    enlight_act_tensor_t *output_tensors[MAX_NUM_OUTPUT];

    // 네트워크 인스턴스 초기화
    inst = (enlight_network_t *)net_inst;
    custom_param = (enlight_custom_postproc_t *)inst->post_proc_extension;

    // 출력 텐서 가져오기
    num_output = enlight_custom_get_output_tensors(custom_param, output_tensors);

    // 출력 텐서의 베이스 주소 설정
    for (i = 0; i < num_output; i++) {
        output_tensors[i]->base = output_base;
    }

    // 커스텀 후처리 초기화
    custom_postproc_init();

    // 로케이션 데이터 저장용 메모리 할당
    float *loc = (float *)malloc(18 * 4 * sizeof(float));
    if (!loc) {
        fprintf(stderr, "Failed to allocate memory for loc\n");
        return -1;
    }

    // 커스텀 후처리 실행
    result = custom_postproc_run(num_output, output_tensors, loc);

    // 결과 복사
    memcpy(custom_loc->loc, loc, 72 * sizeof(float));
    // Lane 정보 출력
    

    // 메모리 해제
    free(loc);

    return num_output;
}
