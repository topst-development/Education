#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <float.h>
#include "enlight_network.h"

#ifdef BARE_METAL_FW_DEV
    extern int _printf(const char *format, ...);
#   define  ENLIGHT_CUSTOM_PRINT  _printf
#else
#   define  ENLIGHT_CUSTOM_PRINT   printf
#endif

#define enlight_custom_err(...)  do {ENLIGHT_CUSTOM_PRINT(__VA_ARGS__); } while(0)
#define enlight_custom_log(...)  do {ENLIGHT_CUSTOM_PRINT(__VA_ARGS__); } while(0)

#ifdef ENLIGHT_CUSTOM_DEBUG
#   define enlight_custom_dbg(...)  do {ENLIGHT_CUSTOM_PRINT(__VA_ARGS__); } while(0)
#else
#   define enlight_custom_dbg(...)  do {} while(0)
#endif

void custom_softmax(float* input, float* output, int axis_len) {
    for (int j = 0; j < 18; j++) {
        for (int k = 0; k < 4; k++) {
            float max_val = input[0 * 72 + j * 4 + k];
            for (int i = 1; i < axis_len; i++) {
                if (input[i * 72 + j * 4 + k] > max_val) {
                    max_val = input[i * 72 + j * 4 + k];
                }
            }
            float sum = 0.0f;
            for (int i = 0; i < axis_len; i++) {
                output[i * 72 + j * 4 + k] = expf(input[i * 72 + j * 4 + k] - max_val);
                sum += output[i * 72 + j * 4 + k];
            }
            for (int i = 0; i < axis_len; i++) {
                output[i * 72 + j * 4 + k] /= sum;
            }
        }
    }
}

void custom_postproc_init() {
    // Initialization code if needed
}
int custom_postproc_run(
    int num_output,
    enlight_act_tensor_t** output_tensors,
    float* loc
) {
    int dims[4];
    enlight_act_tensor_t* tensor = output_tensors[0];

    enlight_get_tensor_dimensions(tensor, dims);
    int batch_size = dims[0];
    int num_classes = dims[1];
    int h = dims[2];
    int w = dims[3];

    
    float* origin_data = (float*)malloc(output_tensors[0]->size * sizeof(float));
    enlight_get_tensor_data(output_tensors[0], origin_data);

    int griding_num = 200;
    float* out_j = (float*)malloc(14472 * sizeof(float));
    float* prob = (float*)malloc(14472 * sizeof(float));

    memcpy(out_j, origin_data, sizeof(float) * 14472);
    for (int i = 0; i < 201; i++) {
        for (int j = 0; j < 18; j++) {
            memcpy(&out_j[i * 72 + (17 - j) * 4], &origin_data[i * 72 + j * 4], sizeof(float) * 4);
        }
    }

    custom_softmax(out_j, prob, 200);

    int* idx = (int*)malloc(griding_num * sizeof(int));
    for (int i = 0; i < griding_num; i++) {
        idx[i] = i + 1;
    }

    for (int j = 0; j < 18; j++) {
        for (int k = 0; k < 4; k++) {
            loc[j * 4 + k] = 0.0f;
            for (int i = 0; i < griding_num; i++) {
                loc[j * 4 + k] += prob[i * 72 + j * 4 + k] * idx[i];
            }
        }
    }

    float* out_j_argmax = (float*)malloc(18 * 4 * sizeof(float));
    for (int j = 0; j < 18; j++) {
        for (int k = 0; k < 4; k++) {
            float max_val = -FLT_MAX;
            int max_idx = -1;
            for (int i = 0; i < griding_num + 1; i++) {
                float value = out_j[i * 72 + j * 4 + k];
                if (value > max_val) {
                    max_val = value;
                    max_idx = i;
                }
            }
            out_j_argmax[j * 4 + k] = max_idx;
        }
    }

    for (int j = 0; j < 18; j++) {
        for (int k = 0; k < 4; k++) {
            if (out_j_argmax[j * 4 + k] == 200) {
                loc[j * 4 + k] = 0;
            }
        }
    }

    // Add x, y coordinate output
    float x_scale = 800.0f / (griding_num - 1);  // Assuming input width is 800
    float y_scale = 288.0f / 17;  // Assuming input height is 288 and 18 anchors
    
    for (int j = 0; j < 18; j++) {
        for (int k = 0; k < 4; k++) {
            if (loc[j * 4 + k] > 0) {  // Valid point
                float x = loc[j * 4 + k] * x_scale;
                float y = j * y_scale;
                
            }
        }
    }

    free(origin_data);
    free(out_j);
    free(prob);
    free(idx);
    free(out_j_argmax);

    return 0;
}
