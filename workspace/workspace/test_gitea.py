#!/usr/bin/env python3
"""Gitea 连接测试脚本"""

import os
import sys
import json
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# 从配置获取 Gitea 信息
GITEA_URL = os.environ.get("GITEA_URL", "http://gitea:3000")
GITEA_TOKEN = os.environ.get("GITEA_TOKEN", "")
GITEA_ORG = os.environ.get("GITEA_ORG", "pandaevo")

def test_gitea_connection():
    """测试 Gitea 连接"""
    results = {
        "gitea_url": GITEA_URL,
        "gitea_org": GITEA_ORG,
        "token_configured": bool(GITEA_TOKEN),
        "tests": []
    }
    
    # 测试 1: 版本 API (无需认证)
    print("=" * 60)
    print("Gitea 连接测试报告")
    print("=" * 60)
    print(f"\n配置信息:")
    print(f"  Gitea URL: {GITEA_URL}")
    print(f"  Gitea Org: {GITEA_ORG}")
    print(f"  Token 已配置: {bool(GITEA_TOKEN)}")
    print()
    
    # 测试 1: 版本 API
    print("测试 1: 版本 API (/api/v1/version) - 无需认证")
    print("-" * 60)
    try:
        url = f"{GITEA_URL}/api/v1/version"
        req = Request(url)
        with urlopen(req, timeout=10) as response:
            status = response.status
            content = response.read().decode('utf-8')
            print(f"  ✓ 连接成功")
            print(f"  HTTP 状态码: {status}")
            print(f"  返回内容: {content}")
            results["tests"].append({
                "name": "version_api",
                "status": "success",
                "http_code": status,
                "response": content
            })
    except HTTPError as e:
        print(f"  ✗ HTTP 错误: {e.code} {e.reason}")
        print(f"  返回内容: {e.read().decode('utf-8') if e.fp else 'N/A'}")
        results["tests"].append({
            "name": "version_api",
            "status": "http_error",
            "http_code": e.code,
            "error": str(e)
        })
    except URLError as e:
        print(f"  ✗ 连接失败: {e.reason}")
        results["tests"].append({
            "name": "version_api",
            "status": "connection_error",
            "error": str(e.reason)
        })
    except Exception as e:
        print(f"  ✗ 未知错误: {e}")
        results["tests"].append({
            "name": "version_api",
            "status": "error",
            "error": str(e)
        })
    print()
    
    # 测试 2: 用户 API (需要认证)
    print("测试 2: 当前用户 API (/api/v1/user) - 需要认证")
    print("-" * 60)
    if GITEA_TOKEN:
        try:
            url = f"{GITEA_URL}/api/v1/user"
            req = Request(url)
            req.add_header("Authorization", f"token {GITEA_TOKEN}")
            with urlopen(req, timeout=10) as response:
                status = response.status
                content = response.read().decode('utf-8')
                print(f"  ✓ 认证成功")
                print(f"  HTTP 状态码: {status}")
                print(f"  返回内容: {content}")
                results["tests"].append({
                    "name": "user_api",
                    "status": "success",
                    "http_code": status,
                    "response": content
                })
        except HTTPError as e:
            print(f"  ✗ HTTP 错误: {e.code} {e.reason}")
            print(f"  返回内容: {e.read().decode('utf-8') if e.fp else 'N/A'}")
            results["tests"].append({
                "name": "user_api",
                "status": "http_error",
                "http_code": e.code,
                "error": str(e)
            })
        except URLError as e:
            print(f"  ✗ 连接失败: {e.reason}")
            results["tests"].append({
                "name": "user_api",
                "status": "connection_error",
                "error": str(e.reason)
            })
        except Exception as e:
            print(f"  ✗ 未知错误: {e}")
            results["tests"].append({
                "name": "user_api",
                "status": "error",
                "error": str(e)
            })
    else:
        print("  ⚠ 跳过: 未配置 GITEA_TOKEN")
        results["tests"].append({
            "name": "user_api",
            "status": "skipped",
            "reason": "No token configured"
        })
    print()
    
    # 测试 3: 组织 API (需要认证)
    print(f"测试 3: 组织 API (/api/v1/orgs/{GITEA_ORG}) - 需要认证")
    print("-" * 60)
    if GITEA_TOKEN:
        try:
            url = f"{GITEA_URL}/api/v1/orgs/{GITEA_ORG}"
            req = Request(url)
            req.add_header("Authorization", f"token {GITEA_TOKEN}")
            with urlopen(req, timeout=10) as response:
                status = response.status
                content = response.read().decode('utf-8')
                print(f"  ✓ 认证成功")
                print(f"  HTTP 状态码: {status}")
                print(f"  返回内容: {content}")
                results["tests"].append({
                    "name": "org_api",
                    "status": "success",
                    "http_code": status,
                    "response": content
                })
        except HTTPError as e:
            print(f"  ✗ HTTP 错误: {e.code} {e.reason}")
            print(f"  返回内容: {e.read().decode('utf-8') if e.fp else 'N/A'}")
            results["tests"].append({
                "name": "org_api",
                "status": "http_error",
                "http_code": e.code,
                "error": str(e)
            })
        except URLError as e:
            print(f"  ✗ 连接失败: {e.reason}")
            results["tests"].append({
                "name": "org_api",
                "status": "connection_error",
                "error": str(e.reason)
            })
        except Exception as e:
            print(f"  ✗ 未知错误: {e}")
            results["tests"].append({
                "name": "org_api",
                "status": "error",
                "error": str(e)
            })
    else:
        print("  ⚠ 跳过: 未配置 GITEA_TOKEN")
        results["tests"].append({
            "name": "org_api",
            "status": "skipped",
            "reason": "No token configured"
        })
    print()
    
    # 测试 4: 组织仓库列表 (需要认证)
    print(f"测试 4: 组织仓库列表 (/api/v1/orgs/{GITEA_ORG}/repos) - 需要认证")
    print("-" * 60)
    if GITEA_TOKEN:
        try:
            url = f"{GITEA_URL}/api/v1/orgs/{GITEA_ORG}/repos"
            req = Request(url)
            req.add_header("Authorization", f"token {GITEA_TOKEN}")
            with urlopen(req, timeout=10) as response:
                status = response.status
                content = response.read().decode('utf-8')
                data = json.loads(content)
                repo_names = [repo.get("name", "unknown") for repo in data] if isinstance(data, list) else data
                print(f"  ✓ 认证成功")
                print(f"  HTTP 状态码: {status}")
                print(f"  仓库数量: {len(repo_names) if isinstance(repo_names, list) else 'N/A'}")
                print(f"  仓库列表: {repo_names[:10]}..." if len(repo_names) > 10 else f"  仓库列表: {repo_names}")
                results["tests"].append({
                    "name": "org_repos_api",
                    "status": "success",
                    "http_code": status,
                    "repo_count": len(repo_names) if isinstance(repo_names, list) else 0,
                    "response": content[:500] + "..." if len(content) > 500 else content
                })
        except HTTPError as e:
            print(f"  ✗ HTTP 错误: {e.code} {e.reason}")
            print(f"  返回内容: {e.read().decode('utf-8') if e.fp else 'N/A'}")
            results["tests"].append({
                "name": "org_repos_api",
                "status": "http_error",
                "http_code": e.code,
                "error": str(e)
            })
        except URLError as e:
            print(f"  ✗ 连接失败: {e.reason}")
            results["tests"].append({
                "name": "org_repos_api",
                "status": "connection_error",
                "error": str(e.reason)
            })
        except Exception as e:
            print(f"  ✗ 未知错误: {e}")
            results["tests"].append({
                "name": "org_repos_api",
                "status": "error",
                "error": str(e)
            })
    else:
        print("  ⚠ 跳过: 未配置 GITEA_TOKEN")
        results["tests"].append({
            "name": "org_repos_api",
            "status": "skipped",
            "reason": "No token configured"
        })
    print()
    
    # 总结
    print("=" * 60)
    print("测试结果总结")
    print("=" * 60)
    success_count = sum(1 for t in results["tests"] if t["status"] == "success")
    error_count = sum(1 for t in results["tests"] if t["status"] in ["error", "http_error", "connection_error"])
    skipped_count = sum(1 for t in results["tests"] if t["status"] == "skipped")
    
    print(f"成功: {success_count}")
    print(f"失败: {error_count}")
    print(f"跳过: {skipped_count}")
    
    if error_count > 0:
        print("\n可能的原因分析:")
        for test in results["tests"]:
            if test["status"] in ["error", "http_error", "connection_error"]:
                print(f"  - {test['name']}: {test.get('error', 'Unknown')}")
    
    # 保存结果到文件
    with open("/workspace/gitea_test_results.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n详细结果已保存到: /workspace/gitea_test_results.json")
    
    return results

if __name__ == "__main__":
    test_gitea_connection()
