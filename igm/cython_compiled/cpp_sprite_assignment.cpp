#include <vector>
#include <cmath>

#define INF (100000000);

using namespace std;

class Vec3{
public:
  float X[3];
  
  Vec3() {X[0] = 0; X[1] = 0; X[2] = 0;}
  explicit Vec3(float* a) {X[0] = a[0]; X[1] = a[1]; X[2] = a[2];}
  Vec3(float x, float y, float z) {X[0] = x; X[1] = y; X[2] = z;}
  
  float operator[](int i){return X[i];}
  const float operator[](int i) const{return X[i];}

  Vec3& operator=(float* a) {X[0] = a[0]; X[1] = a[1]; X[2] = a[2]; return *this;}
  Vec3& operator=(Vec3& a) {X[0] = a[0]; X[1] = a[1]; X[2] = a[2]; return *this;}

  Vec3 operator+(const Vec3& w) const {return Vec3(X[0] + w.X[0], X[1] + w.X[1], X[2] + w.X[2]); }
  Vec3 operator-(const Vec3& w) const {return Vec3(X[0] - w.X[0], X[1] - w.X[1], X[2] - w.X[2]); }
  
  Vec3 operator-() const {return Vec3(-X[0], -X[1], -X[2]); }

  Vec3 operator*(const float w) const {return Vec3(X[0] * w, X[1] * w, X[2] * w); }
  Vec3 operator/(const float w) const {return Vec3(X[0] / w, X[1] / w, X[2] / w); }

  Vec3& operator+=(const Vec3& w){X[0] += w[0]; X[1] += w[1]; X[2] += w[2]; return *this;}
  Vec3& operator-=(const Vec3& w){X[0] -= w[0]; X[1] -= w[1]; X[2] -= w[2]; return *this;}

  Vec3& operator+=(float w){X[0] += w; X[1] += w; X[2] += w; return *this;}
  Vec3& operator-=(float w){X[0] -= w; X[1] -= w; X[2] -= w; return *this;}

  Vec3& operator*=(const float w) {X[0] *= w; X[1] *= w; X[2] *= w; return *this;}
  Vec3& operator/=(const float w) {X[0] /= w; X[1] /= w; X[2] /= w; return *this;}

  float dot(const Vec3& w) const { return X[0]*w[0] + X[1]*w[1] + X[2]*w[2]; }
  float normsq() const { return dot(*this); }
  float norm() const { return sqrt(normsq()); }
};

float dot(const Vec3& a, const Vec3& b) { return a.dot(b); }
float normsq(const Vec3& a) { return a.normsq(); }
float norm(const Vec3& a) { return a.norm(); }


float gyration_radius_sq(const vector<Vec3>& crd)
{
  Vec3 r_mean(0.0f, 0.0f, 0.0f);
  int n = crd.size();
  for (int i = 0; i < n; ++i)
    r_mean += crd[i];
  r_mean /= n;

  float rg = 0;
  for (int i = 0; i < n; ++i)
    rg += normsq(crd[i] - r_mean);
  return (rg / n);
}

void get_combination(const vector<vector<float*> >& all_copies,
                     int* copies_num,
                     int n_regions,
                     int k, 
                     vector<Vec3>& comb,
                     vector<int>& copy_idx)
{
  for (int i = 0; i < n_regions; ++i)
  {
    int si = k % copies_num[i];
    k /= copies_num[i];
    comb[i] = all_copies[i][si];
    copy_idx[i] = si;
  }
}

void get_rg2s_cpp(float* crds,
                  int n_struct,
                  int n_bead,
                  int n_regions, 
                  int* copies_num,
                  float* rg2s,
                  int* copy_idxs,
                  int* min_struct)
{
  
  vector<vector<float*> > all_copies(n_bead); // all coordinates
  vector<Vec3> current(n_regions); // coords of only one combination
  vector<int> copy_idx(n_regions); // copies selection for current combination
  
  float min_rg2 = INF; // absolute minimum

  // prepare all_copies and compute the total
  // number of possible combinations
  int n_combinations = 1; 
  for (int i = 0; i < n_regions; ++i)
  {
    all_copies[i].resize(copies_num[i]);
    n_combinations *= copies_num[i];
  }

  // loop through structures
  for (int s = 0; s < n_struct; ++s)
  {
    // set all_copies coordinates
    int k = 0;
    for (int i = 0; i < n_regions; ++i)
    {
      for (int j = 0; j < copies_num[i]; ++j)
      {
        all_copies[i][j] = crds + k*n_struct*3 + s*3;
        k += 1;
      }
    }

    // explore all the combinations
    float min_struct_rg2 = INF;
    vector<int> min_copy_idx(n_regions, -1);
    for (int i = 0; i < n_combinations; ++i)
    {
      get_combination(all_copies, copies_num, n_regions, i, current, copy_idx);
      float rg2 = gyration_radius_sq(current);
      if (rg2 < min_struct_rg2){
        min_struct_rg2 = rg2;
        min_copy_idx.swap(copy_idx);
      }
    }

    // save results and check minimum
    rg2s[s] = min_struct_rg2;
    for (int i = 0; i < n_regions; ++i)
    {
      copy_idxs[n_regions*s + i] = min_copy_idx[i];
    }
    if (min_struct_rg2 < min_rg2)
    {
      min_rg2 = min_struct_rg2;
      *min_struct = s;
    }
  }
}
